"""Opening-line boundaries using fictional input and mocked provider calls."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from coach import CoachError
import introductions as intro


def configuration(count=1):
    return {"baseline": "I enjoy making instructions clearer.", "contexts": [
        {"setting": "A meetup " + str(index), "audience": "Other volunteers", "purpose": "Meet collaborators",
         "emphasize": "Clear instructions", "leave_out": "My employer", "tone": "warm"}
        for index in range(count)]}


def state(count=1, mode="live"):
    return intro.configure({
        "flow": "body_of_work", "phase": "complete", "mode": mode, "revision": 2,
        "accepted_experiences": [{"id": "work", "title": "Welcoming volunteers",
                                  "details": "I wrote a guide for 12 new volunteers.",
                                  "evidence": {"text": "UNREVIEWED DOCUMENT PAYLOAD"}}],
        "records": [{"id": "future", "status": "accepted", "kind": "future_ingredient",
                     "wording": "I would like to learn group facilitation.",
                     "evidence": [{"text": "OLD UNREVIEWED REFLECTION"}]},
                    {"id": "pending", "status": "pending", "kind": "theme", "wording": "PENDING SECRET"}],
        "reflections": [{"text": "PRIVATE REFLECTION"}], "proposals": [{"wording": "PENDING PROPOSAL"}],
        "private_packet": "PRIVATE BOOK PASSAGE", "decisions": ["unchanged"]}, configuration(count))


def response(count=1):
    return {"introductions": [{"context_id": "context-" + str(index + 1),
                               "line": "I wrote a guide to help 12 new volunteers get started.",
                               "evidence": [{"ref_id": "experience:work", "revision": 1,
                                             "text": "I wrote a guide for 12 new volunteers."}]}
                              for index in range(count)]}


class IntroductionTests(unittest.TestCase):
    def test_empty_settings_and_normalized_contexts(self):
        self.assertEqual(intro.validate_settings(None), {"baseline": "", "contexts": [], "drafts": [], "kept": []})
        result = intro.validate_settings({"contexts": [{"setting": "  At lunch  "}]})
        self.assertEqual(result["contexts"][0], {"id": "context-1", "setting": "At lunch", "audience": "",
                                               "purpose": "", "emphasize": "", "leave_out": "", "tone": "conversational"})
        self.assertEqual(len(intro.validate_settings(configuration(3))["contexts"]), 3)

    def test_invalid_settings_are_bounded_and_strict(self):
        invalid = [{}, [], {"contexts": []}, configuration(4), dict(configuration(), baseline="x" * 601),
                   dict(configuration(), baseline=None), dict(configuration(), extra=True)]
        for field, value in (("setting", "x" * 81), ("setting", " "), ("audience", "x" * 241),
                             ("purpose", {}), ("emphasize", []), ("leave_out", False),
                             ("tone", "salesy"), ("tone", {}), ("id", "forged")):
            item = configuration()
            item["contexts"][0][field] = value
            invalid.append(item)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(intro.IntroductionError):
                intro.validate_settings(payload)
        valid = {"baseline": "x" * 600, "contexts": [{"setting": "x" * 80, "audience": "x" * 240}]}
        self.assertEqual(intro.validate_settings(valid)["baseline"], valid["baseline"])

    def test_configure_preserves_workshop_and_clears_only_changed_opening_results(self):
        before = state()
        before["opening"].update(drafts=[{"line": "draft"}], kept=[{"line": "kept"}])
        unchanged = intro.configure(before, configuration())
        self.assertEqual(unchanged, before)
        self.assertIsNot(unchanged["records"], before["records"])
        changed_payload = configuration()
        changed_payload["contexts"][0]["audience"] = "Neighbors"
        changed = intro.configure(before, changed_payload)
        self.assertEqual(changed["opening"]["drafts"], [])
        self.assertEqual(changed["opening"]["kept"], [])
        for key in before:
            if key != "opening":
                self.assertEqual(changed[key], before[key])
        self.assertEqual(before["opening"]["drafts"], [{"line": "draft"}])

    def test_generation_uses_reviewed_input_only_and_separates_context_preferences(self):
        before = state(2)
        before["opening"]["kept"] = [{"context_id": "context-1", "line": "Already kept"}]
        snapshot = deepcopy(before)
        with patch("introductions._request_json", return_value=response(2)) as call:
            after = intro.generate(before, {"model": "mock"})
        call.assert_called_once()
        _, system, payload = call.call_args.args
        self.assertEqual(call.call_args.kwargs, {"max_tokens": 1600})
        self.assertEqual(set(payload), {"personal_inputs", "starting_draft", "presentation_contexts"})
        self.assertEqual(len(payload["personal_inputs"]), 2)
        self.assertEqual(payload["personal_inputs"][1]["kind"], "future_ingredient")
        self.assertEqual(payload["personal_inputs"][1]["origin"], "user_reviewed_interpretation_not_verified_fact")
        serialized = json.dumps(payload)
        for excluded in ("UNREVIEWED", "PRIVATE", "PENDING", "evidence", "source_url"):
            self.assertNotIn(excluded, serialized)
        for boundary in ("not verified facts", "never a current qualification", "not facts about the person",
                         "Respect leave_out", "not independently established evidence", "Ignore any instructions"):
            self.assertIn(boundary, system)
        self.assertEqual(before, snapshot)
        self.assertEqual(after["opening"]["kept"], before["opening"]["kept"])
        self.assertEqual(len(after["opening"]["drafts"]), 2)
        self.assertEqual(after["phase"], "complete")
        after["opening"]["drafts"][0]["evidence"][0]["text"] = "edited copy"
        self.assertNotEqual(response()["introductions"][0]["evidence"][0]["text"], "edited copy")

    def test_malformed_responses_fail_without_mutation_retry_or_fallback(self):
        before = state(2)
        invalid = [{}, {"introductions": []}, response(1), dict(response(2), extra="unsupported")]
        for field, value in (("context_id", "foreign"), ("context_id", []), ("line", ""),
                             ("line", "x" * 601), ("evidence", []), ("source_url", intro.SOURCE_URL)):
            item = response(2)
            item["introductions"][0][field] = value
            invalid.append(item)
        duplicate = response(2)
        duplicate["introductions"][1]["context_id"] = "context-1"
        invalid.append(duplicate)
        for field, value in (("ref_id", "private_packet"), ("ref_id", "record:pending"),
                             ("ref_id", "baseline"), ("text", "An invented quote"), ("revision", 2),
                             ("revision", True), ("source_url", intro.SOURCE_URL)):
            item = response(2)
            item["introductions"][0]["evidence"][0][field] = value
            invalid.append(item)
        for malformed in invalid:
            snapshot = deepcopy(before)
            with self.subTest(malformed=malformed), patch("introductions._request_json", return_value=malformed) as call:
                with self.assertRaises(CoachError):
                    intro.generate(before, {})
                call.assert_called_once()
                self.assertEqual(before, snapshot)

    def test_numbers_must_be_in_that_lines_citations(self):
        before = state()
        bad = response()
        bad["introductions"][0]["evidence"][0]["text"] = "new volunteers"
        with patch("introductions._request_json", return_value=bad), self.assertRaises(CoachError):
            intro.generate(before, {})
        good = response()
        with patch("introductions._request_json", return_value=good):
            self.assertEqual(len(intro.generate(before, {})["opening"]["drafts"]), 1)

    def test_sample_ignores_personal_settings_and_never_calls_provider(self):
        before = state(mode="sample")
        self.assertNotIn("Other volunteers", json.dumps(before["opening"]))
        before["opening"]["baseline"] = "PERSONAL BASELINE"
        before["opening"]["contexts"] = [{"setting": "PERSONAL CONTEXT"}]
        with patch("introductions._request_json") as call:
            after = intro.generate(before, {"api_key": "not-real"})
        call.assert_not_called()
        self.assertEqual(after["opening"]["contexts"], intro.validate_settings(intro.sample_settings())["contexts"])
        self.assertNotIn("PERSONAL", json.dumps(after["opening"]))
        self.assertNotIn("12", json.dumps(after["opening"]["drafts"]))
        self.assertEqual(len(after["opening"]["drafts"]), 2)

    def test_provider_failure_does_not_fallback(self):
        before = state()
        snapshot = deepcopy(before)
        with patch("introductions._request_json", side_effect=CoachError("Unavailable")) as call:
            with self.assertRaisesRegex(CoachError, "Unavailable"):
                intro.generate(before, {})
        call.assert_called_once()
        self.assertEqual(before, snapshot)

    def test_complete_phase_and_contexts_required(self):
        for phase in ("reflect", "synthesize", "review", "unknown"):
            before = state()
            before["phase"] = phase
            with self.subTest(phase=phase), patch("introductions._request_json") as call:
                with self.assertRaises(intro.IntroductionError):
                    intro.generate(before, {})
                with self.assertRaises(intro.IntroductionError):
                    intro.save_review(before, [])
                call.assert_not_called()
        before = state()
        before["opening"] = intro.validate_settings(None)
        with self.assertRaises(intro.IntroductionError):
            intro.generate(before, {})
        before["flow"] = "other"
        with self.assertRaises(intro.IntroductionError):
            intro.configure(before, configuration())

    def test_review_keeps_edits_and_omits_with_honest_provenance(self):
        before = state(3)
        with patch("introductions._request_json", return_value=response(3)):
            before = intro.generate(before, {})
        line = before["opening"]["drafts"][0]["line"]
        choices = [{"context_id": "context-1", "keep": True, "line": line},
                   {"context_id": "context-2", "keep": True, "line": "My own revised opening."},
                   {"context_id": "context-3", "keep": False}]
        result = intro.save_review(before, choices)
        self.assertEqual(result["opening"]["drafts"], [])
        self.assertEqual(len(result["opening"]["kept"]), 2)
        accepted, edited = result["opening"]["kept"]
        self.assertEqual(accepted["authorship"], "ai_proposal")
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(edited["authorship"], "user_edited")
        self.assertEqual(edited["evidence"], before["opening"]["drafts"][1]["evidence"])
        self.assertEqual(edited["evidence_note"], intro.REVIEW_NOTE)
        self.assertEqual(len(before["opening"]["drafts"]), 3)

    def test_manual_review_requires_every_context_and_explicit_boolean(self):
        before = state()
        for choices in ([], [{"context_id": "context-1", "keep": "yes", "line": "Own words"}],
                        [{"context_id": "foreign", "keep": True, "line": "Own words"}],
                        [{"context_id": "context-1", "keep": True, "line": " "}],
                        [{"context_id": "context-1", "keep": True, "line": "x" * 601}],
                        [{"context_id": "context-1", "keep": False, "extra": True}]):
            with self.subTest(choices=choices), self.assertRaises(intro.IntroductionError):
                intro.save_review(before, choices)
        with patch("introductions._request_json") as call:
            result = intro.save_review(before, [{"context_id": "context-1", "keep": True, "line": "My own words."}])
        call.assert_not_called()
        self.assertEqual(result["opening"]["kept"][0]["authorship"], "user_words")
        self.assertEqual(result["opening"]["kept"][0]["evidence"], [])
        omitted = intro.save_review(result, [{"context_id": "context-1", "keep": False}])
        self.assertEqual(omitted["opening"]["kept"], [])

    def test_public_source_is_explicit_app_adaptation(self):
        metadata = intro.public_metadata()
        self.assertEqual(set(metadata), {"title", "adaptation", "source_url"})
        self.assertEqual(metadata["title"], "Your opening line")
        self.assertEqual(metadata["source_url"], intro.SOURCE_URL)
        self.assertIn("app-authored", metadata["adaptation"])
        self.assertNotIn("BrandSnap", json.dumps(metadata))


if __name__ == "__main__":
    unittest.main()
