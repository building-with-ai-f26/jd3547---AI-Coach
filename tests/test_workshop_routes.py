"""Workshop integration boundaries, with fictional input and no provider calls."""

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import create_app
from coach import CoachError
from workshop import STEPS, build_own_words


HEADERS = {"X-Coach-Request": "1", "Origin": "http://localhost"}
EXPERIENCES = [{"title": "Volunteer guide", "details": "I wrote a guide to help new volunteers get started."}]


class WorkshopRouteTests(unittest.TestCase):
    def setUp(self):
        network = patch("coach.httpx.post", side_effect=AssertionError("No network in deterministic checks"))
        network.start()
        self.addCleanup(network.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.packet = Path(self.directory.name) / "source.json"
        self.packet.write_text(json.dumps({"method_id": "body-of-work-mini-v1", "methods": [
            {"id": name, "title": name, "locator": "Chapter " + str(i),
             "guidance": "PRIVATE_GUIDE_SENTINEL", "supporting_passages": ["PRIVATE_PASSAGE_SENTINEL"]}
            for i, name in enumerate(("roots", "ingredients", "contribution"), 1)]}))
        self.app = create_app({"TESTING": True, "OPENROUTER_API_KEY": "", "OPENROUTER_MODEL": "test/model",
                               "BODY_OF_WORK_SOURCE_PATH": str(self.packet)})
        self.client = self.app.test_client()
        self.client.get("/api/workshop/config")

    def post(self, path, data):
        return self.client.post("/api/workshop/" + path, json=data, headers=HEADERS)

    def start(self, mode="live"):
        version = self.client.get("/api/workshop/state").json["current_version"]
        response = self.post("start", {"mode": mode, "version": version, "experiences": EXPERIENCES})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def answered(self, mode="sample"):
        state = self.start(mode)
        for step in STEPS:
            response = self.post("answer", {"version": state["version"], "answer": "I want to help volunteers feel welcome.", "skip": False})
            self.assertEqual(response.status_code, 200, response.json)
            state = response.json
        self.assertEqual(state["phase"], "synthesize")
        return state

    def test_private_packet_never_in_config_state_or_export(self):
        state = self.start()
        for path in ("/api/workshop/config", "/api/workshop/state", "/api/workshop/export", "/api/export"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            text = response.get_data(as_text=True)
            self.assertNotIn("PRIVATE_GUIDE_SENTINEL", text)
            self.assertNotIn("PRIVATE_PASSAGE_SENTINEL", text)
            self.assertNotIn(str(self.packet), text)
        restored = self.client.get("/api/workshop/state").json["state"]
        self.assertEqual(restored, state)

    def test_no_key_own_words_end_to_end_and_review(self):
        state = self.answered("live")
        response = self.post("synthesize", {"version": state["version"], "own_words": False})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/workshop/state").json["state"], state)
        state = self.post("synthesize", {"version": state["version"], "own_words": True}).json
        self.assertEqual(state["phase"], "review")
        decisions = [{"id": p["id"], "decision": "accept"} for p in state["proposals"]]
        done = self.post("review", {"version": state["version"], "decisions": decisions})
        self.assertEqual(done.status_code, 200, done.json)
        self.assertEqual(done.json["phase"], "complete")
        self.assertTrue(done.json["records"])
        exported = self.client.get("/api/workshop/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("attachment", exported.headers["Content-Disposition"])

    def test_phase_version_and_cross_origin_guards(self):
        state = self.start()
        self.assertEqual(self.post("review", {"version": state["version"], "decisions": []}).status_code, 400)
        response = self.post("answer", {"version": state["version"], "answer": "Welcoming newcomers matters to me."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post("answer", {"version": state["version"], "answer": "stale answer"}).status_code, 409)
        self.assertEqual(self.post("start", {"mode": "sample", "version": state["version"]}).status_code, 409)
        response = self.client.post("/api/workshop/answer", json={}, headers={"X-Coach-Request": "1", "Origin": "https://elsewhere.example"})
        self.assertEqual(response.status_code, 403)

    def test_missing_packet_disables_personal_but_allows_sample(self):
        app = create_app({"TESTING": True, "OPENROUTER_API_KEY": "", "BODY_OF_WORK_SOURCE_PATH": str(self.packet.parent / "missing")})
        client = app.test_client()
        config = client.get("/api/workshop/config").json
        self.assertFalse(config["available"])
        self.assertEqual(client.post("/api/workshop/start", json={"mode": "live", "version": 0, "experiences": EXPERIENCES}, headers=HEADERS).status_code, 503)
        response = client.post("/api/workshop/start", json={"mode": "sample", "version": 0}, headers=HEADERS)
        self.assertEqual(response.status_code, 200)

    def test_quick_exercise_cannot_silently_replace_workshop(self):
        state = self.start()
        response = self.client.post("/api/start", json={"mode": "sample"}, headers=HEADERS)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/api/workshop/state").json["state"], state)

    def test_no_import_of_unapproved_or_invented_cards(self):
        response = self.post("start", {"mode": "live", "version": 0, "use_document": True, "experience_ids": ["forged"]})
        self.assertEqual(response.status_code, 400)
        invalid = deepcopy(EXPERIENCES)
        invalid[0]["evidence"] = {"text": "pretend source"}
        self.assertEqual(self.post("start", {"mode": "live", "version": 0, "experiences": invalid}).status_code, 400)

    def test_only_selected_approved_pdf_cards_transfer(self):
        from test_app import StubCoach
        app = create_app({"TESTING": True, "OPENROUTER_API_KEY": "test-not-a-real-key",
                          "BODY_OF_WORK_SOURCE_PATH": str(self.packet)}, coach=StubCoach())
        client = app.test_client()
        client.get("/api/config")
        with patch("app.extract_pdf", return_value=[{"page": 1, "text": "Fictional input."}]):
            response = client.post("/api/documents", data={"file": (BytesIO(b"%PDF-fictional"), "fictional.pdf")},
                                   headers=HEADERS, content_type="multipart/form-data")
            response.request.environ["wsgi.input"].close()
        self.assertEqual(response.status_code, 200)
        uploaded = response.json
        cards = [{"id": c["id"], "include": True, "title": c["title"], "details": c["details"]} for c in uploaded["experience_cards"]]
        reviewed = client.post("/api/documents/review", json={"version": uploaded["version"], "cards": cards}, headers=HEADERS).json
        selected_id = reviewed["accepted_experiences"][0]["id"]
        response = client.post("/api/workshop/start", json={"version": reviewed["version"], "mode": "live",
                               "use_document": True, "experience_ids": [selected_id]}, headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["accepted_experiences"], [reviewed["accepted_experiences"][0]])

    def test_sample_ignores_personal_input(self):
        state = self.start("sample")
        state = self.post("answer", {"version": state["version"], "answer": "PRIVATE_INPUT_NOT_FOR_SAMPLE", "skip": False}).json
        self.assertNotIn("PRIVATE_INPUT_NOT_FOR_SAMPLE", json.dumps(state))
        self.assertNotIn(EXPERIENCES[0]["details"], json.dumps(state))

    def test_revise_preserves_earlier_answers_and_clears_dependent_results(self):
        state = self.answered()
        state = self.post("synthesize", {"version": state["version"], "own_words": True}).json
        earlier = deepcopy(state["reflections"][:2])
        state = self.post("revise", {"version": state["version"], "step_id": STEPS[2]["id"]}).json
        self.assertEqual(state["reflections"], earlier)
        self.assertEqual(state["phase"], "reflect")
        self.assertFalse(state["proposals"])
        self.assertFalse(state["records"])

    def test_failed_model_keeps_answers_and_can_use_own_words(self):
        self.app.config["OPENROUTER_API_KEY"] = "test-not-a-real-key"
        state = self.answered("live")
        with patch("app.workshop.synthesize", side_effect=CoachError("The service could not connect.")):
            response = self.post("synthesize", {"version": state["version"], "own_words": False})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get("/api/workshop/state").json["state"], state)
        response = self.post("synthesize", {"version": state["version"], "own_words": True})
        self.assertEqual(response.status_code, 200)

    def test_reset_discards_a_delayed_synthesis(self):
        self.app.config["OPENROUTER_API_KEY"] = "test-not-a-real-key"
        state = self.answered("live")
        started, release = threading.Event(), threading.Event()
        results = []

        def delayed(snapshot, packet, settings):
            started.set()
            if not release.wait(5):
                raise AssertionError("Test timed out")
            return build_own_words(snapshot)

        with patch("app.workshop.synthesize", side_effect=delayed):
            thread = threading.Thread(target=lambda: results.append(self.post("synthesize", {"version": state["version"], "own_words": False})))
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(self.post("answer", {"version": state["version"], "answer": "double click"}).status_code, 409)
                self.client.post("/api/reset", json={}, headers=HEADERS)
            finally:
                release.set()
                thread.join(3)
        self.assertEqual(results[0].status_code, 409)
        self.assertIsNone(self.client.get("/api/workshop/state").json["state"])


if __name__ == "__main__":
    unittest.main()
