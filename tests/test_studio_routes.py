"""Story-library session, import and security boundaries with fictional inputs."""
from copy import deepcopy
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import patch

from app import create_app
from coach import CoachError
import production


HEADERS = {"X-Coach-Request": "1", "Origin": "http://localhost"}
EXPERIENCE = {"title": "Volunteer onboarding", "details": "I wrote a guide for new library volunteers.",
              "reflection": {"situation": "New volunteers could not find the instructions.",
                             "action": "I asked volunteers what was confusing and rewrote the guide.",
                             "outcome": "The group used the new guide.", "learning": "I enjoy making a first step clearer."}}


class StudioRouteTests(unittest.TestCase):
    def setUp(self):
        network = patch("coach.httpx.post", side_effect=AssertionError("No paid calls in tests"))
        self.network = network.start()
        self.addCleanup(network.stop)
        self.app = create_app({"TESTING": True, "PRODUCTION": False, "RENDER_PROXY": False,
                               "TRUSTED_HOSTS": ["localhost"], "RATE_LIMIT_ENABLED": False,
                               "OPENROUTER_API_KEY": "", "OPENROUTER_MODEL": "test/model",
                               "BODY_OF_WORK_SOURCE_PATH": "/nonexistent/private-guide.json"})
        self.client = self.app.test_client()
        self.assertEqual(self.client.get("/api/studio/config").status_code, 200)

    def post(self, name, data, client=None):
        return (client or self.client).post("/api/studio/" + name, json=data, headers=HEADERS)

    def start(self, mode="live"):
        version = self.client.get("/api/studio/state").json["current_version"]
        response = self.post("start", {"version": version, "mode": mode})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def test_manual_library_survives_refresh_and_export_restore_without_key(self):
        state = self.start()
        added = self.post("experience", dict(EXPERIENCE, version=state["version"]))
        self.assertEqual(added.status_code, 200, added.json)
        state = added.json
        saved = self.post("core", {"version": state["version"], "text": "I enjoy making first steps clearer."})
        self.assertEqual(saved.status_code, 200, saved.json)
        self.assertEqual(self.client.get("/api/studio/state").json["state"], saved.json)
        exported = self.client.get("/api/studio/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("attachment", exported.headers["Content-Disposition"])
        self.assertEqual(self.client.get("/api/export").json, exported.json)
        self.assertEqual(self.client.post("/api/reset", json={}, headers=HEADERS).status_code, 200)
        restored = self.post("restore", {"version": 0, "payload": exported.json})
        self.assertEqual(restored.status_code, 200, restored.json)
        self.assertEqual(restored.json["experiences"][0]["details"], EXPERIENCE["details"])
        self.assertEqual(restored.json["core"]["text"], saved.json["core"]["text"])
        self.network.assert_not_called()

    def test_sample_drafts_review_and_context_adaptation(self):
        state = self.start("sample")
        experience = state["experiences"][0]
        origin = self.post("generate", {"version": state["version"], "kind": "origin", "experience_id": experience["id"]})
        self.assertEqual(origin.status_code, 200, origin.json)
        self.assertIsNotNone(origin.json["pending"])
        self.assertEqual(origin.json["origins"], [])
        kept = self.post("review", {"version": origin.json["version"], "decision": "keep"})
        self.assertEqual(kept.status_code, 200, kept.json)
        adapted = self.post("generate", {"version": kept.json["version"], "kind": "adaptation",
                            "origin_id": kept.json["origins"][0]["id"],
                            "context": {"audience": "Community organizers", "setting": "Networking", "purpose": "Explore volunteering"}})
        self.assertEqual(adapted.status_code, 200, adapted.json)
        self.assertTrue(adapted.json["pending"]["angle"])
        self.assertTrue(adapted.json["pending"]["question"])
        omitted = self.post("review", {"version": adapted.json["version"], "decision": "omit"})
        self.assertEqual(omitted.status_code, 200, omitted.json)
        self.assertEqual(omitted.json["adaptations"], [])
        self.network.assert_not_called()

    def test_version_origin_and_session_isolation(self):
        state = self.start()
        added = self.post("experience", dict(EXPERIENCE, version=state["version"]))
        self.assertEqual(added.status_code, 200)
        self.assertEqual(self.post("experience", dict(EXPERIENCE, version=state["version"])).status_code, 409)
        second = self.app.test_client()
        self.assertIsNone(second.get("/api/studio/state").json["state"])
        self.assertEqual(self.post("core", {"version": added.json["version"], "text": "Not mine"}, second).status_code, 409)
        for name in ("experience", "core", "generate", "review", "restore", "start", "documents/review"):
            with self.subTest(name=name):
                response = self.client.post("/api/studio/" + name, json={},
                                            headers={"X-Coach-Request": "1", "Origin": "https://elsewhere.example"})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.post("start", {"version": added.json["version"], "mode": "sample"}).status_code, 409)
        self.assertEqual(self.client.get("/api/studio/state").json["state"], added.json)

    def test_invalid_restore_and_provider_error_preserve_saved_work(self):
        state = self.start()
        state = self.post("experience", dict(EXPERIENCE, version=state["version"])).json
        self.app.config["OPENROUTER_API_KEY"] = "fictional-test-key"
        with patch("app.studio.generate", side_effect=CoachError("The AI service could not finish.")):
            failed = self.post("generate", {"version": state["version"], "kind": "origin", "experience_id": state["experiences"][0]["id"]})
        self.assertEqual(failed.status_code, 502)
        self.assertFalse(self.client.get("/api/studio/state").json["working"])
        self.assertEqual(self.client.get("/api/studio/state").json["state"], state)
        invalid = self.post("restore", {"version": state["version"], "replace": True, "payload": {"format": "other", "library": {}}})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.get("/api/studio/state").json["state"], state)

    def test_reset_discards_a_delayed_model_response(self):
        state = self.start("sample")
        entered, release = threading.Event(), threading.Event()
        result = []

        def slow(old, data, config):
            entered.set()
            release.wait(5)
            return deepcopy(old)

        def invoke():
            result.append(self.post("generate", {"version": state["version"], "kind": "core"}))

        with patch("app.studio.generate", side_effect=slow):
            worker = threading.Thread(target=invoke)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                duplicate = self.post("generate", {"version": state["version"], "kind": "core"})
                self.assertEqual(duplicate.status_code, 409)
                self.assertEqual(self.client.post("/api/reset", json={}, headers=HEADERS).status_code, 200)
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(result[0].status_code, 409)
        self.assertIsNone(self.client.get("/api/studio/state").json["state"])

    def test_pdf_review_only_approved_cards_enter_library(self):
        state = self.start()
        self.app.config["OPENROUTER_API_KEY"] = "fictional-test-key"
        pages = [{"page": 1, "text": "I wrote a guide for new library volunteers."}]
        cards = [{"title": "Volunteer guide", "details": pages[0]["text"], "evidence": {"page": 1, "text": pages[0]["text"]}}]
        with patch("app.extract_pdf", return_value=pages), patch("coach.LiveCoach.extract_experiences", return_value=cards):
            uploaded = self.client.post("/api/studio/documents", data={"version": str(state["version"]),
                                        "file": (BytesIO(b"%PDF-fictional"), "fictional.pdf")}, headers=HEADERS,
                                        content_type="multipart/form-data")
        self.assertEqual(uploaded.status_code, 200, uploaded.json)
        self.assertEqual(uploaded.json["experiences"], [])
        candidate = uploaded.json["import_review"][0]
        approved = self.post("documents/review", {"version": uploaded.json["version"], "cards": [
            {"id": candidate["id"], "include": True, "title": candidate["title"], "details": candidate["details"]}]})
        self.assertEqual(approved.status_code, 200, approved.json)
        self.assertEqual(len(approved.json["experiences"]), 1)
        self.assertEqual(approved.json["experiences"][0]["evidence"]["page"], 1)
        self.assertEqual(approved.json["import_review"], [])

    def test_new_paid_routes_share_production_limits(self):
        self.assertTrue({"/api/studio/generate", "/api/studio/documents"}.issubset(production.PAID_PATHS))
        app = create_app({"TESTING": True, "PRODUCTION": True, "RENDER_PROXY": False,
                          "TRUSTED_HOSTS": ["coach.example"], "AI_REQUEST_LIMIT": 1,
                          "OPENROUTER_API_KEY": "", "BODY_OF_WORK_SOURCE_PATH": "/nonexistent"})
        client = app.test_client()
        headers = {"X-Coach-Request": "1", "Origin": "https://coach.example"}
        client.post("/api/studio/generate", json={}, headers=headers, base_url="https://coach.example")
        blocked = client.post("/api/studio/documents", json={}, headers=headers, base_url="https://coach.example")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked.headers)
        self.network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
