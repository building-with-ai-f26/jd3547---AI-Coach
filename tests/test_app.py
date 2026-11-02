"""Application-state and local-boundary tests; never contact a model service."""

from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch

from app import COOKIE, MAX_CHARS, create_app
from coach import CoachError, SAMPLE, SAMPLE_PROPOSAL, SAMPLE_QUESTION, SOURCE_IDS, valid_text


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
