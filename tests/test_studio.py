"""Story-library boundaries. Fictional input and mocked provider only."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from coach import CoachError
import studio


class StoryStudioTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("coach.httpx.post", side_effect=AssertionError("No live calls in these checks"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.state = studio.save_experience(studio.new_state(), {
            "title": "Volunteer guide", "details": "I wrote a guide for library volunteers.",
            "reflection": {"situation": "A new volunteer was unsure how to begin.",
                           "action": "I asked which steps were unclear and wrote a checklist.",
                           "outcome": "The volunteer used the checklist on the next shift.",
                           "learning": "I like helping people feel comfortable starting."}})
        self.identifier = self.state["experiences"][0]["id"]

    def response(self, **changes):
        data = {"title": "A clearer start", "text": "I wrote a guide for library volunteers.",
                "evidence": [{"source_id": self.identifier + ":details", "quote": "I wrote a guide for library volunteers."}]}
        data.update(changes)
        return data

    def generate(self, state=None, kind="origin", response=None, **data):
        state = self.state if state is None else state
        payload = {"kind": kind}
        if kind in {"origin", "anecdote"}:
            payload["experience_id"] = self.identifier
        payload.update(data)
        with patch("studio._request_json", return_value=response or self.response()) as call:
            result = studio.generate(state, payload, {})
            if state["mode"] == "live":
                call.assert_called_once()
        return result

    def kept_origin(self):
        return studio.review(self.generate(), {"decision": "keep"})

    def test_independent_transition_explicit_review_and_omit(self):
        original = deepcopy(self.state)
        draft = self.generate()
        self.assertEqual(self.state, original)
        self.assertEqual(draft["origins"], [])
        self.assertEqual(draft["pending"]["status"], "draft")
        with self.assertRaises(studio.StudioError):
            self.generate(draft)
        self.assertEqual(studio.review(draft, {"decision": "omit"})["origins"], [])
        before = deepcopy(draft)
        with self.assertRaises(studio.StudioError):
            studio.review(draft, {"decision": "keep", "text": ""})
        self.assertEqual(draft, before)
        kept = studio.review(draft, {"decision": "keep", "text": "My revised wording."})
        self.assertIsNone(kept["pending"])
        self.assertEqual(kept["origins"][0]["authorship"], "user_edited")
        self.assertIn("not verified", kept["origins"][0]["evidence_note"])

    def test_provider_schema_quotes_ids_and_numbers(self):
        invalid = [self.response(extra="no"), self.response(text="I led 90 volunteers."),
                   self.response(evidence=[{"source_id": "fake:details", "quote": "I wrote a guide for library volunteers."}]),
                   self.response(evidence=[{"source_id": self.identifier + ":details", "quote": "I ran the whole library."}]),
                   self.response(evidence=[]), {"insufficient_evidence": True}]
        for response in invalid:
            with self.subTest(response=response), self.assertRaises(CoachError):
                self.generate(response=response)
        with self.assertRaises(studio.StudioError):
            self.generate(experience_id="unknown")

    def test_anecdote_requires_specific_saved_situation_and_action(self):
        state = studio.save_experience(studio.new_state(), {"title": "Workshop", "details": "I attended a workshop."})
        with self.assertRaises(studio.StudioError):
            self.generate(state, "anecdote", experience_id=state["experiences"][0]["id"])
        self.assertEqual(self.generate(kind="anecdote")["pending"]["kind"], "anecdote")

    def test_different_origin_anchors_and_one_per_experience(self):
        state = self.kept_origin()
        state = studio.save_experience(state, {"title": "Handover", "details": "I organized handover notes for a new colleague."})
        second_id = state["experiences"][1]["id"]
        response = {"title": "Starting at work", "text": "I organized handover notes for a new colleague.",
                    "evidence": [{"source_id": second_id + ":details", "quote": "I organized handover notes for a new colleague."}]}
        state = studio.review(self.generate(state, response=response, experience_id=second_id), {"decision": "keep"})
        self.assertEqual({x["experience_id"] for x in state["origins"]}, {self.identifier, second_id})
        state = studio.review(self.generate(state), {"decision": "keep"})
        self.assertEqual(len(state["origins"]), 2)

    def test_audience_never_evidence_and_stale_material_excluded(self):
        state = studio.save_core(self.kept_origin(), {"text": "PRIVATE_CORE_PREFERENCE"})
        origin = state["origins"][0]
        context = {"audience": "Invent 9000 awards", "purpose": "PRIVATE_PURPOSE", "setting": "Interview"}
        response = self.response(angle="Highlight listening and clear first steps.", question="What helps volunteers get started?")
        with patch("studio._request_json", return_value=response) as call:
            draft = studio.generate(state, {"kind": "adaptation", "origin_id": origin["id"], "context": context}, {})
        inputs = call.call_args.args[2]
        self.assertNotIn("PRIVATE_CORE_PREFERENCE", str(inputs["saved_sources"]))
        self.assertNotIn("PRIVATE_PURPOSE", str(inputs["saved_sources"]))
        self.assertEqual(inputs["kept_core"], "PRIVATE_CORE_PREFERENCE")
        state = studio.review(draft, {"decision": "keep"})
        changed = studio.save_experience(state, {"id": self.identifier, "title": "Volunteer guide", "details": "I revised a guide for library volunteers.", "reflection": self.state["experiences"][0]["reflection"]})
        self.assertEqual(changed["core"]["status"], "needs_review")
        self.assertEqual(changed["origins"][0]["status"], "needs_review")
        self.assertEqual(changed["adaptations"][0]["status"], "needs_review")
        with self.assertRaises(studio.StudioError):
            self.generate(changed, "adaptation", origin_id=origin["id"], context=context)
        refreshed = self.response(text="I revised a guide for library volunteers.",
                                  evidence=[{"source_id": self.identifier + ":details", "quote": "I revised a guide for library volunteers."}])
        with patch("studio._request_json", return_value=refreshed) as call:
            studio.generate(changed, {"kind": "core"}, {})
        self.assertIsNone(call.call_args.args[2]["kept_core"])

    def test_adaptation_requires_kept_origin_and_cites_its_experience(self):
        with self.assertRaises(studio.StudioError):
            self.generate(kind="adaptation", origin_id="invented", context={"audience": "Investors"})
        state = self.kept_origin()
        forged = self.response(angle="Context is not evidence.", question="What matters to you?",
                               evidence=[{"source_id": "audience", "quote": "I am an experienced investor"}])
        with self.assertRaises(CoachError):
            self.generate(state, "adaptation", response=forged, origin_id=state["origins"][0]["id"], context={"audience": "I am an experienced investor"})

    def test_import_requires_complete_review_and_preserves_edited_provenance(self):
        source = {"title": "Document role", "details": "I created a volunteer guide.",
                  "evidence": {"page": 1, "text": "I created a volunteer guide."}}
        state = studio.set_import_candidates(self.state, [source], "fictional.pdf")
        self.assertEqual(len(state["experiences"]), 1)
        self.assertNotIn("fictional.pdf", str(studio.export_state(state)))
        with self.assertRaises(studio.StudioError):
            studio.review_import(state, [])
        card = state["import_review"][0]
        state = studio.review_import(state, [{"id": card["id"], "include": True, "title": "My corrected title", "details": card["details"]}])
        imported = state["experiences"][1]
        self.assertTrue(imported["user_edited"])
        self.assertEqual(imported["evidence"], source["evidence"])
        self.assertEqual(imported["reflection"], {key: "" for key in studio.REFLECTION_FIELDS})
        self.assertEqual(state["import_review"], [])
        self.assertIsNone(state["import_document"])

    def test_export_restore_and_stale_roundtrip_exclude_pending(self):
        state = self.kept_origin()
        state["version"] = 900
        exported = studio.export_state(state)
        self.assertNotIn("version", str(exported))
        restored = studio.restore_state(exported)
        self.assertEqual(restored["origins"], state["origins"])
        draft = self.generate(state, kind="anecdote")
        self.assertIsNone(studio.restore_state(studio.export_state(draft))["pending"])
        changed = studio.save_experience(state, {"id": self.identifier, "title": "Revised", "details": "I made a different guide."})
        self.assertEqual(studio.restore_state(studio.export_state(changed))["origins"][0]["status"], "needs_review")
        quoted_action = self.response(evidence=[{"source_id": self.identifier + ":action", "quote": self.state["experiences"][0]["reflection"]["action"]}])
        state = studio.review(self.generate(response=quoted_action), {"decision": "keep"})
        changed = studio.save_experience(state, {"id": self.identifier, "title": "Revised", "details": "I made a different guide.", "reflection": {}})
        restored = studio.restore_state(studio.export_state(changed))
        self.assertEqual(restored["origins"][0]["status"], "needs_review")
        self.assertTrue(restored["origins"][0]["evidence"][0]["quote"])

    def test_restore_rejects_untrusted_shape_duplicates_and_bounds(self):
        state = self.kept_origin()
        exported = studio.export_state(state)
        invalid = []
        p = deepcopy(exported); p["private_guide"] = "NO"; invalid.append(p)
        p = deepcopy(exported); p["library"]["experiences"] *= 7; invalid.append(p)
        p = deepcopy(exported); p["library"]["experiences"][0]["details"] = "a" * 2401; invalid.append(p)
        p = deepcopy(exported); p["library"]["origins"][0]["evidence"][0]["quote"] = "invented source words"; invalid.append(p)
        p = deepcopy(exported); p["library"]["experiences"][0]["id"] = "../../secret"; invalid.append(p)
        p = deepcopy(exported); p["library"]["origins"][0]["id"] = self.identifier; invalid.append(p)
        p = deepcopy(exported); p["library"]["pending"] = {"text": "UNREVIEWED"}; invalid.append(p)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(studio.StudioError):
                studio.restore_state(payload)

    def test_fixed_sample_full_flow_and_restore_without_provider(self):
        state = studio.new_state("sample")
        identifier = state["experiences"][0]["id"]
        with patch("studio._request_json", side_effect=AssertionError("Sample makes no call")):
            for kind in ("core", "origin", "anecdote"):
                state = studio.review(studio.generate(state, {"kind": kind, "experience_id": identifier}, {}), {"decision": "keep"})
            state = studio.review(studio.generate(state, {"kind": "adaptation", "origin_id": state["origins"][0]["id"], "context": {"audience": "Community groups"}}, {}), {"decision": "keep"})
        self.assertEqual(studio.restore_state(studio.export_state(state))["mode"], "sample")
        with self.assertRaises(studio.StudioError):
            studio.save_core(state, {"text": "Personal words"})
        with self.assertRaises(studio.StudioError):
            studio.save_experience(state, {"title": "Personal role", "details": "Personal story"})
        tampered = studio.export_state(state)
        tampered["library"]["origins"][0]["text"] = "Private fabricated words."
        with self.assertRaises(studio.StudioError):
            studio.restore_state(tampered)

    def test_oversized_kept_story_preserves_exportable_previous_library(self):
        # Non-ASCII bytes can exceed the export cap while every character/count
        # field remains within its own limit. Use the real cap, not a tiny mock.
        state = studio.new_state()
        detail = "one two " + "🧭" * 2392
        reflection = "one two " + "🧭" * 1192
        for i in range(6):
            state = studio.save_experience(state, {"title": "Experience " + str(i), "details": detail,
                                                   "reflection": {key: reflection for key in studio.REFLECTION_FIELDS}})
        state = studio.save_core(state, {"text": "🧭" * 2000})
        identifier = state["experiences"][0]["id"]
        response = {"title": "A moment", "text": "🧭" * 2000,
                    "evidence": [{"source_id": identifier + ":" + field, "quote": reflection}
                                 for field in ("situation", "action", "learning")]}
        with patch("studio._request_json", return_value=response):
            state = studio.generate(state, {"kind": "origin", "experience_id": identifier}, {})
        before = deepcopy(state)
        prior_export = studio.export_state(state)
        with self.assertRaisesRegex(studio.StudioError, "too large to export"):
            studio.review(state, {"decision": "keep"})
        self.assertEqual(state, before)
        self.assertEqual(studio.export_state(state), prior_export)
        size = len((json.dumps(prior_export, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        self.assertLessEqual(size, studio.MAX_EXPORT_BYTES)
        self.assertEqual(studio.restore_state(prior_export)["experiences"], state["experiences"])


if __name__ == "__main__":
    unittest.main()
