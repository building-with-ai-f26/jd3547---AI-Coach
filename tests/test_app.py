"""Application-state and local-boundary tests; never contact a model service."""

from copy import deepcopy
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import patch

from app import COOKIE, MAX_CHARS, create_app
from coach import CoachError, SAMPLE, SAMPLE_PROPOSAL, SAMPLE_QUESTION, SOURCE_IDS, valid_text
from documents import DocumentError, MAX_PDF_BYTES
from test_documents import FICTIONAL_EXPERIENCES, fictional_cv_pdf


HEADERS = {"X-Coach-Request": "1", "Origin": "http://localhost"}
TEST_KEY = "unit-test-key-not-a-real-credential"
BACKGROUND = "I built a volunteer guide. I also organized a team handover."
ANSWER = "I asked newcomers what they needed first."


class StubCoach:
    def __init__(self):
        self.calls = []

    def question(self, background, settings):
        self.calls.append(("question", background))
        return "What did you contribute in both situations?"

    def extract_experiences(self, pages, settings):
        self.calls.append(("extract", deepcopy(pages)))
        return deepcopy(FICTIONAL_EXPERIENCES)

    def propose(self, background, question, answer, settings):
        self.calls.append(("propose", background, question, answer))
        return {
            "theme": "Helping people get started",
            "statement": "I make the first step easier to understand.",
            "evidence": [{"text": answer, "from": "answer"}],
            "source_ids": list(SOURCE_IDS),
        }


class BlockingCoach(StubCoach):
    def __init__(self, block_on="propose"):
        super().__init__()
        self.block_on = block_on
        self.started = threading.Event()
        self.release = threading.Event()

    def _wait(self, operation):
        if self.block_on == operation:
            self.started.set()
            if not self.release.wait(5):
                raise CoachError("Test provider wait expired.")

    def question(self, background, settings):
        self._wait("question")
        return super().question(background, settings)

    def propose(self, background, question, answer, settings):
        self._wait("propose")
        return super().propose(background, question, answer, settings)

    def extract_experiences(self, pages, settings):
        self._wait("extract")
        return super().extract_experiences(pages, settings)


class AppTests(unittest.TestCase):
    def setUp(self):
        # Accidental real requests fail immediately, including if a real .env exists.
        self.network = patch("coach.httpx.post", side_effect=AssertionError("Network disabled in unit tests"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.coach = StubCoach()
        self.app = create_app({"TESTING": True, "OPENROUTER_API_KEY": TEST_KEY,
                               "OPENROUTER_MODEL": "test/model"}, coach=self.coach)
        self.client = self.app.test_client()

    def post(self, path, data, client=None, headers=None):
        return (client or self.client).post(path, json=data, headers=HEADERS if headers is None else headers)

    def start(self, mode="sample", client=None):
        response = self.post("/api/start", {"mode": mode, "background": BACKGROUND}, client)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def review_state(self, mode="sample"):
        state = self.start(mode)
        response = self.post("/api/answer", {"version": state["version"], "answer": ANSWER})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def export(self, client=None):
        response = (client or self.client).get("/api/export")
        self.assertEqual(response.status_code, 200)
        return response, json.loads(response.get_data(as_text=True))

    def upload(self, client=None, headers=None, document=None, filename="fictional-cv.pdf", initialize=True):
        client = client or self.client
        if initialize:
            client.get("/api/config")
        response = client.post("/api/documents", data={"file": (BytesIO(fictional_cv_pdf() if document is None else document), filename)},
                               headers=HEADERS if headers is None else headers, content_type="multipart/form-data")
        # Werkzeug's test builder may spool its generated HTTP envelope. This is
        # separate from the app's uploaded-file stream and needs closing in tests.
        response.request.environ["wsgi.input"].close()
        return response

    def import_state(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def card_review(self, state, selected=None):
        return {"version": state["version"], "cards": [
            {"id": card["id"], "title": card["title"], "details": card["details"],
             "include": selected is None or index in selected}
            for index, card in enumerate(state["experience_cards"])]}

    def test_document_upload_proposes_cards_but_cannot_export_before_review(self):
        state = self.import_state()
        self.assertEqual(state["stage"], "import_review")
        self.assertEqual(state["document"]["page_count"], 2)
        self.assertEqual(state["document"]["name"], "fictional-cv.pdf")
        self.assertEqual(state["accepted_experiences"], [])
        self.assertIsNone(state["background"])
        self.assertEqual(len({card["id"] for card in state["experience_cards"]}), 3)
        self.assertNotIn("pages", state)
        self.assertNotIn("FICTIONAL SAMPLE CV", json.dumps(state))
        self.assertEqual(self.client.get("/api/export").status_code, 409)
        self.assertEqual([call[0] for call in self.coach.calls], ["extract"])

    def test_document_edits_and_rejections_limit_export_and_next_model_calls(self):
        state = self.import_state()
        review = self.card_review(state, selected={1})
        review["cards"][1]["title"] = "  Helping new volunteers  "
        review["cards"][1]["details"] = "I created a guide to help new volunteers find their first task."
        response = self.post("/api/documents/review", review)
        self.assertEqual(response.status_code, 200)
        imported = response.get_json()
        self.assertEqual(imported["stage"], "imported")
        self.assertEqual(imported["experience_cards"], [])
        approved = imported["accepted_experiences"]
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["title"], "Helping new volunteers")
        self.assertTrue(approved[0]["user_edited"])
        self.assertEqual(approved[0]["evidence"], state["experience_cards"][1]["evidence"])
        exported = self.export()[1]
        self.assertEqual(exported["exercise"], imported)
        self.assertNotIn("hackathon", json.dumps(exported))
        self.assertNotIn("survey data", json.dumps(exported))
        started = self.post("/api/start", {"mode": "live", "use_document": True, "version": imported["version"],
                                           "background": "Do not include this client-supplied text"})
        self.assertEqual(started.status_code, 200)
        question = started.get_json()
        expected = approved[0]["title"] + "\n" + approved[0]["details"]
        self.assertEqual(question["background"], expected)
        self.assertEqual(question["accepted_experiences"], approved)
        self.assertEqual(self.coach.calls[-1], ("question", expected))
        response = self.post("/api/answer", {"version": question["version"], "answer": ANSWER})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["document"], imported["document"])
        self.assertEqual(self.coach.calls[-1][1], expected)
        complete = self.post("/api/review", {"version": response.json["version"], "decision": "accept"})
        self.assertEqual(complete.json["accepted_experiences"], approved)
        self.assertNotIn("hackathon", json.dumps(self.export()[1]))

    def test_document_review_rejects_invented_duplicate_missing_and_changed_evidence(self):
        state = self.import_state()
        valid = self.card_review(state)
        invalid = []
        changed = deepcopy(valid); changed["cards"][0]["id"] = "invented"; invalid.append(changed)
        changed = deepcopy(valid); changed["cards"][1]["id"] = changed["cards"][0]["id"]; invalid.append(changed)
        changed = deepcopy(valid); changed["cards"].pop(); invalid.append(changed)
        changed = deepcopy(valid); changed["cards"][0]["evidence"] = {"page": 9, "text": "Invented"}; invalid.append(changed)
        changed = deepcopy(valid); changed["cards"][0]["include"] = "yes"; invalid.append(changed)
        changed = deepcopy(valid); changed["cards"][0]["title"] = "x" * 121; invalid.append(changed)
        changed = deepcopy(valid); changed["cards"][0]["details"] = "x" * 601; invalid.append(changed)
        invalid.append(self.card_review(state, selected=set()))
        for payload in invalid:
            with self.subTest(payload=str(payload)[:70]):
                self.assertEqual(self.post("/api/documents/review", payload).status_code, 400)
        accepted = self.post("/api/documents/review", valid)
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(any(card["user_edited"] for card in accepted.json["accepted_experiences"]))
        self.assertEqual(self.post("/api/documents/review", valid).status_code, 409)
        self.assertEqual(self.post("/api/start", {"mode": "live", "use_document": True,
                                                "version": state["version"]}).status_code, 409)

    def test_pending_or_missing_document_cannot_be_used_for_coaching(self):
        self.assertEqual(self.post("/api/start", {"mode": "live", "use_document": True, "version": 1}).status_code, 409)
        state = self.import_state()
        self.assertEqual(self.post("/api/start", {"mode": "live", "use_document": True,
                                                "version": state["version"]}).status_code, 409)
        self.assertEqual([call[0] for call in self.coach.calls], ["extract"])

    def test_excluded_cards_can_have_empty_text_but_selected_cards_cannot(self):
        state = self.import_state()
        payload = self.card_review(state, selected={1})
        for index in (0, 2):
            payload["cards"][index].update(title="", details="")
        invalid = deepcopy(payload)
        invalid["cards"][1]["details"] = " "
        self.assertEqual(self.post("/api/documents/review", invalid).status_code, 400)
        response = self.post("/api/documents/review", payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["accepted_experiences"]), 1)
        self.assertEqual(response.json["accepted_experiences"][0]["id"], payload["cards"][1]["id"])

    def test_upload_requires_live_key_cookie_and_exactly_one_pdf(self):
        self.assertEqual(self.upload(initialize=False).status_code, 409)
        self.app.config["OPENROUTER_API_KEY"] = ""
        self.assertEqual(self.upload().status_code, 503)
        self.app.config["OPENROUTER_API_KEY"] = TEST_KEY
        for filename, data in (("notes.txt", b"text"), ("empty.pdf", b""), ("fake.pdf", b"not PDF")):
            with self.subTest(filename=filename):
                self.assertEqual(self.upload(filename=filename, document=data).status_code, 400)
        for form in ({"other": (BytesIO(b"%PDF-"), "file.pdf")},
                     {"file": [(BytesIO(b"%PDF-"), "a.pdf"), (BytesIO(b"%PDF-"), "b.pdf")]},
                     {"file": (BytesIO(b"%PDF-"), "file.pdf"), "extra": "unexpected"}):
            response = self.client.post("/api/documents", data=form, headers=HEADERS, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.coach.calls, [])

    def test_upload_multipart_has_same_origin_protection_and_json_limits_remain(self):
        for headers in ({}, {"X-Coach-Request": "1", "Origin": "https://attacker.example"},
                        {"X-Coach-Request": "1", "Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.upload(headers=headers).status_code, 403)
        self.assertEqual(self.post("/api/documents", {}).status_code, 403)
        self.assertEqual(self.client.post("/api/start", data={"file": (BytesIO(b"x"), "a.pdf")},
                                         headers=HEADERS, content_type="multipart/form-data").status_code, 403)
        self.assertEqual(self.upload(document=b"%PDF-" + b"x" * MAX_PDF_BYTES).status_code, 413)
        self.assertEqual(self.post("/api/start", {"mode": "live", "background": "x" * 50000}).status_code, 413)

    def test_upload_stream_stays_in_memory_and_does_not_expose_key(self):
        observed = []
        from app import MemoryUploadRequest
        original = MemoryUploadRequest._get_file_stream
        def stream(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result
        with patch.object(MemoryUploadRequest, "_get_file_stream", stream), patch("app.extract_pdf", return_value=[{"page": 1, "text": "Fictional text"}]):
            response = self.upload(document=b"%PDF-" + b"x" * 700000, filename="../../fictional.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(observed and all(isinstance(item, BytesIO) for item in observed))
        self.assertEqual(response.json["document"]["name"], "fictional.pdf")
        self.assertNotIn(TEST_KEY, response.get_data(as_text=True))
        cookie = self.client.get_cookie(COOKIE).value
        self.assertNotIn("fictional", cookie)
        self.assertNotIn(TEST_KEY, cookie)

    def test_upload_parse_or_model_failure_releases_operation_for_retry(self):
        with patch("app.extract_pdf", side_effect=DocumentError("Please paste readable text.")):
            self.assertEqual(self.upload().status_code, 400)
        with patch.object(self.coach, "extract_experiences", side_effect=CoachError("Please retry.")):
            self.assertEqual(self.upload().status_code, 502)
        self.assertEqual(self.upload().status_code, 200)

    def test_upload_reset_discards_delayed_extraction_and_blocks_duplicate(self):
        blocker = BlockingCoach(block_on="extract")
        app = create_app({"TESTING": True, "OPENROUTER_API_KEY": TEST_KEY, "OPENROUTER_MODEL": "test/model"}, coach=blocker)
        client = app.test_client()
        client.get("/api/config")
        worker_client = app.test_client()
        worker_client.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(self.upload(client=worker_client, initialize=False)))
        worker.start()
        try:
            self.assertTrue(blocker.started.wait(3))
            self.assertEqual(self.upload(client=client, initialize=False).status_code, 409)
            self.assertEqual(self.post("/api/reset", {}, client=client).status_code, 200)
        finally:
            blocker.release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0].status_code, 409)
        self.assertEqual(client.get("/api/export").status_code, 400)
        self.assertEqual(worker_client.get("/api/export").status_code, 400)
        self.assertEqual([call[0] for call in blocker.calls], ["extract"])

    def test_reset_during_pdf_parsing_prevents_sending_pages_to_model(self):
        self.client.get("/api/config")
        worker_client = self.app.test_client()
        worker_client.set_cookie(COOKIE, self.client.get_cookie(COOKIE).value)
        started = threading.Event()
        release = threading.Event()
        responses = []

        def delayed_parse(data):
            started.set()
            if not release.wait(5):
                raise AssertionError("Parser wait expired")
            return [{"page": 1, "text": "Fictional experience that should not be sent."}]

        with patch("app.extract_pdf", side_effect=delayed_parse):
            worker = threading.Thread(target=lambda: responses.append(self.upload(client=worker_client, initialize=False)))
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(self.post("/api/reset", {}).status_code, 200)
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0].status_code, 409)
        self.assertEqual(self.coach.calls, [])

    def test_sample_ignores_submitted_personal_inputs_and_never_calls_provider(self):
        state = self.start()
        self.assertEqual(state["background"], SAMPLE["background"])
        self.assertEqual(state["question"], SAMPLE_QUESTION)
        response = self.post("/api/answer", {"version": state["version"], "answer": "Malicious replacement"})
        state = response.get_json()
        self.assertEqual(state["answer"], SAMPLE["answer"])
        self.assertEqual(state["proposal"], SAMPLE_PROPOSAL)
        self.assertIsNone(state["accepted"])
        self.assertEqual(self.coach.calls, [])

    def test_accept_promotes_pending_proposal_and_export_labels_sample(self):
        state = self.review_state()
        proposal = deepcopy(state["proposal"])
        before = self.export()[1]["exercise"]
        self.assertIsNone(before["accepted"])
        response = self.post("/api/review", {"version": state["version"], "decision": "accept"})
        completed = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(completed["stage"], "complete")
        self.assertEqual(completed["accepted"], proposal)
        self.assertIsNone(completed["proposal"])
        self.assertEqual(completed["version"], state["version"] + 1)
        exported, payload = self.export()
        self.assertTrue(payload["fictional_sample"])
        self.assertIn("no AI call", payload["note"])
        self.assertEqual(payload["exercise"], completed)
        self.assertIn("attachment", exported.headers["Content-Disposition"])

    def test_edit_is_explicit_and_does_not_mutate_shared_sample(self):
        original = deepcopy(SAMPLE_PROPOSAL)
        state = self.review_state()
        response = self.post("/api/review", {"version": state["version"], "decision": "edit",
                                             "theme": "  My own theme  ", "statement": "  My own wording.  "})
        self.assertEqual(response.status_code, 200)
        accepted = response.get_json()["accepted"]
        self.assertEqual(accepted["theme"], "My own theme")
        self.assertEqual(accepted["statement"], "My own wording.")
        self.assertEqual(SAMPLE_PROPOSAL, original)
        self.post("/api/reset", {})
        self.assertEqual(self.review_state()["proposal"], original)

    def test_reject_leaves_no_accepted_claim_in_export(self):
        state = self.review_state()
        response = self.post("/api/review", {"version": state["version"], "decision": "reject"})
        self.assertEqual(response.status_code, 200)
        exported = self.export()[1]["exercise"]
        self.assertEqual(exported["decision"], "reject")
        self.assertIsNone(exported["accepted"])
        self.assertIsNone(exported["proposal"])

    def test_live_uses_only_submitted_current_exercise_and_labels_export(self):
        state = self.review_state("live")
        self.assertEqual(state["background"], BACKGROUND)
        self.assertEqual(state["answer"], ANSWER)
        self.assertEqual(self.coach.calls, [("question", BACKGROUND),
            ("propose", BACKGROUND, "What did you contribute in both situations?", ANSWER)])
        self.assertFalse(self.export()[1]["fictional_sample"])

    def test_live_without_key_is_503_but_sample_works(self):
        self.app.config["OPENROUTER_API_KEY"] = ""
        self.assertFalse(self.client.get("/api/config").get_json()["live_ready"])
        response = self.post("/api/start", {"mode": "live", "background": BACKGROUND})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.coach.calls, [])
        self.start("sample")

    def test_placeholder_key_does_not_enable_live_mode(self):
        self.app.config["OPENROUTER_API_KEY"] = "replace-with-your-api-key"
        self.assertFalse(self.client.get("/api/config").get_json()["live_ready"])

    def test_invalid_backgrounds_are_rejected_before_model_call(self):
        for value in (None, "", " \n ", 13, [], {"text": BACKGROUND}, "x" * (MAX_CHARS + 1)):
            with self.subTest(value=repr(value)[:30]):
                response = self.post("/api/start", {"mode": "live", "background": value})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.coach.calls, [])

    def test_invalid_answer_releases_operation_for_valid_retry(self):
        state = self.start("live")
        bad = self.post("/api/answer", {"version": state["version"], "answer": " "})
        self.assertEqual(bad.status_code, 400)
        retry = self.post("/api/answer", {"version": state["version"], "answer": ANSWER})
        self.assertEqual(retry.status_code, 200)

    def test_reset_during_invalid_answer_validation_discards_old_operation(self):
        state = self.start("live")
        worker_client = self.app.test_client()
        worker_client.set_cookie(COOKIE, self.client.get_cookie(COOKIE).value)
        started = threading.Event()
        release = threading.Event()
        responses = []

        def delayed_validation(value, maximum):
            if value == " ":
                started.set()
                if not release.wait(5):
                    raise AssertionError("Validation wait expired")
            return valid_text(value, maximum)

        with patch("app.valid_text", side_effect=delayed_validation):
            worker = threading.Thread(target=lambda: responses.append(self.post("/api/answer",
                {"version": state["version"], "answer": " "}, client=worker_client)))
            worker.start()
            try:
                self.assertTrue(started.wait(2), "Validation did not begin")
                self.assertEqual(self.post("/api/reset", {}).status_code, 200)
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0].status_code, 409)
        self.assertEqual(self.client.get("/api/export").status_code, 400)
        self.assertEqual(worker_client.get("/api/export").status_code, 400)

    def test_stale_boolean_and_duplicate_versions_cannot_advance_state(self):
        state = self.start("live")
        for version in (state["version"] - 1, True, str(state["version"]), None):
            with self.subTest(version=version):
                response = self.post("/api/answer", {"version": version, "answer": ANSWER})
                self.assertEqual(response.status_code, 409)
        good = self.post("/api/answer", {"version": state["version"], "answer": ANSWER})
        self.assertEqual(good.status_code, 200)
        duplicate = self.post("/api/answer", {"version": state["version"], "answer": ANSWER})
        self.assertEqual(duplicate.status_code, 409)
        review_version = good.get_json()["version"]
        self.assertEqual(self.post("/api/review", {"version": review_version, "decision": "accept"}).status_code, 200)
        self.assertEqual(self.post("/api/review", {"version": review_version, "decision": "reject"}).status_code, 409)
        self.assertEqual(len(self.coach.calls), 2)

    def test_invalid_review_preserves_pending_proposal(self):
        state = self.review_state()
        for payload in ({"decision": "delete"}, {"decision": "edit", "theme": "", "statement": "ok"},
                        {"decision": "edit", "theme": "x" * 161, "statement": "ok"}):
            with self.subTest(payload=payload):
                response = self.post("/api/review", dict(payload, version=state["version"]))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.export()[1]["exercise"], state)

    def test_provider_failure_preserves_question_and_allows_retry(self):
        state = self.start("live")
        with patch.object(self.coach, "propose", side_effect=CoachError("Please retry.")):
            response = self.post("/api/answer", {"version": state["version"], "answer": ANSWER})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.export()[1]["exercise"], state)
        self.assertEqual(self.post("/api/answer", {"version": state["version"], "answer": ANSWER}).status_code, 200)

    def test_sessions_are_isolated_and_reset_removes_export(self):
        self.start()
        other = self.app.test_client()
        self.assertEqual(other.get("/api/export").status_code, 400)
        self.assertEqual(self.post("/api/answer", {"version": 1, "answer": ANSWER}, client=other).status_code, 409)
        self.assertEqual(self.post("/api/reset", {}).status_code, 200)
        self.assertEqual(self.client.get("/api/export").status_code, 400)

    def test_key_and_personal_text_are_not_in_cookie_or_config(self):
        response = self.post("/api/start", {"mode": "live", "background": BACKGROUND})
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn(BACKGROUND, cookie)
        self.assertNotIn(TEST_KEY, cookie)
        self.assertNotIn(TEST_KEY, response.get_data(as_text=True))
        self.assertNotIn(TEST_KEY, self.client.get("/api/config").get_data(as_text=True))
        self.assertNotIn(BACKGROUND, self.client.get("/api/config").get_data(as_text=True))
        self.assertNotIn(TEST_KEY, self.export()[0].get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_cross_site_missing_header_and_wrong_content_type_posts_fail(self):
        payload = {"mode": "sample"}
        bad_headers = ({}, {"X-Coach-Request": "0"},
                       {"X-Coach-Request": "1", "Origin": "https://attacker.example"},
                       {"X-Coach-Request": "1", "Sec-Fetch-Site": "cross-site"})
        for headers in bad_headers:
            with self.subTest(headers=headers):
                self.assertEqual(self.post("/api/start", payload, headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/api/start", data=json.dumps(payload),
                                         content_type="text/plain", headers=HEADERS).status_code, 403)
        self.assertEqual(self.client.get("/api/export").status_code, 400)

    def test_malformed_json_and_oversized_request_are_errors(self):
        response = self.client.post("/api/start", data="{bad", content_type="application/json", headers=HEADERS)
        self.assertEqual(response.status_code, 400)
        response = self.post("/api/start", {"mode": "live", "background": "x" * 50000})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.coach.calls, [])

    def test_environment_and_source_files_are_not_served(self):
        for path in ("/.env", "/.env.example", "/app.py", "/coach.py", "/content/method.json", "/static/../.env"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(TEST_KEY, response.get_data(as_text=True))

    def test_untrusted_host_is_rejected(self):
        self.assertEqual(self.client.get("/api/config", headers={"Host": "attacker.example"}).status_code, 400)

    def test_duplicate_inflight_answer_makes_only_one_provider_call(self):
        blocker = BlockingCoach()
        app = create_app({"TESTING": True, "OPENROUTER_API_KEY": TEST_KEY,
                          "OPENROUTER_MODEL": "test/model"}, coach=blocker)
        client = app.test_client()
        state = self.start("live", client=client)
        worker_client = app.test_client()
        worker_client.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(self.post("/api/answer",
            {"version": state["version"], "answer": ANSWER}, client=worker_client)))
        worker.start()
        try:
            self.assertTrue(blocker.started.wait(2), "Model stub did not begin")
            duplicate = self.post("/api/answer", {"version": state["version"], "answer": ANSWER}, client=client)
            self.assertEqual(duplicate.status_code, 409)
        finally:
            blocker.release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0].status_code, 200)
        self.assertEqual([call[0] for call in blocker.calls].count("propose"), 1)

    def test_reset_discards_delayed_question_and_answer(self):
        for operation in ("question", "propose"):
            with self.subTest(operation=operation):
                blocker = BlockingCoach(block_on=operation)
                app = create_app({"TESTING": True, "OPENROUTER_API_KEY": TEST_KEY,
                                  "OPENROUTER_MODEL": "test/model"}, coach=blocker)
                client = app.test_client()
                # The browser loads config first; its cookie must exist before
                # the very first slow model call so reset can identify that call.
                config = client.get("/api/config")
                self.assertEqual(config.status_code, 200)
                self.assertIsNotNone(client.get_cookie(COOKIE))
                self.assertEqual(client.get("/api/export").status_code, 400)
                state = self.start("live", client=client) if operation == "propose" else None
                old_sid = client.get_cookie(COOKIE).value
                worker_client = app.test_client()
                worker_client.set_cookie(COOKIE, old_sid)
                path = "/api/start" if operation == "question" else "/api/answer"
                data = {"mode": "live", "background": BACKGROUND} if operation == "question" else {
                    "version": state["version"], "answer": ANSWER}
                responses = []
                worker = threading.Thread(target=lambda: responses.append(self.post(path, data, client=worker_client)))
                worker.start()
                try:
                    self.assertTrue(blocker.started.wait(2), "Model stub did not begin")
                    self.assertEqual(self.post("/api/reset", {}, client=client).status_code, 200)
                finally:
                    blocker.release.set()
                    worker.join(3)
                self.assertFalse(worker.is_alive())
                self.assertEqual(responses[0].status_code, 409)
                self.assertEqual(client.get("/api/export").status_code, 400)
                self.assertEqual(worker_client.get("/api/export").status_code, 400)


if __name__ == "__main__":
    unittest.main()
