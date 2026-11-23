"""Workshop mechanics only: fictional inputs and mocked model transport."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coach import CoachError
import workshop as w


def completed_answers(mode="live", skipped=()):
    state = w.new_state(mode, w.SAMPLE_EXPERIENCES)
    for step in w.STEPS:
        state = w.advance(state, w.SAMPLE_ANSWERS[step["id"]], skip=step["id"] in skipped)
    return state


def proposal(kind="root", ref="roots_value", wording="Making it easier for newcomers to belong"):
    methods = {"root": "roots", "ingredient": "ingredients", "future_ingredient": "ingredients", "direction": "contribution", "theme": "ingredients"}
    return {"kind": kind, "wording": wording,
            "evidence": [{"ref_id": ref, "revision": 1, "text": w.SAMPLE_ANSWERS[ref]}],
            "method_ids": [methods[kind]]}


def packet():
    return {"method_id": w.METHOD_ID, "methods": [dict(method, guidance="Private reviewed method guidance.", supporting_passages=["Private source passage."]) for method in w.METHODS]}


class WorkshopTests(unittest.TestCase):
    def test_progression_and_skip_are_explicit_and_non_mutating(self):
        initial = w.new_state("live", w.SAMPLE_EXPERIENCES)
        after = w.advance(initial, "ignored", skip=True)
        self.assertEqual(initial["reflections"], [])
        self.assertEqual(after["reflections"][0]["status"], "skipped")
        self.assertEqual(after["reflections"][0]["text"], "")
        self.assertNotIn("roots_value", [item["id"] for item in w.personal_context(after)])
        self.assertEqual(completed_answers()["phase"], "synthesize")
        with self.assertRaises(w.WorkshopError):
            w.advance(completed_answers(), "too late")
        with self.assertRaises(w.WorkshopError):
            w.advance(initial, "", skip="yes")

    def test_sample_never_uses_personal_inputs_or_model(self):
        state = w.new_state("sample", [{"private": "real life"}])
        self.assertEqual(state["accepted_experiences"], w.SAMPLE_EXPERIENCES)
        for step in w.STEPS:
            state = w.advance(state, "MY REAL LIFE")
        self.assertNotIn("MY REAL LIFE", json.dumps(state))
        with patch("workshop._request_json") as call:
            result = w.synthesize(state, None, {})
        call.assert_not_called()
        self.assertTrue(w.export_state(result)["fictional_sample"])
        self.assertTrue(all(item["authorship"] == "user_words" for item in result["proposals"]))

    def test_revising_clears_dependent_proposals_and_prevents_stale_citations(self):
        before = w.build_own_words(completed_answers())
        changed = w.revise(before, "ingredient_current")
        self.assertEqual(changed["revision"], 2)
        self.assertEqual(changed["step_index"], 3)
        self.assertEqual([entry["id"] for entry in changed["reflections"]], ["roots_value", "roots_example", "roots_service"])
        self.assertEqual(changed["proposals"], [])
        self.assertEqual(changed["records"], [])
        for step in w.STEPS[3:]:
            changed = w.advance(changed, w.SAMPLE_ANSWERS[step["id"]])
        stale = proposal("ingredient", "ingredient_current")
        with self.assertRaises(CoachError):
            w.validate_proposals({"proposals": [stale]}, changed)
        stale["evidence"][0]["revision"] = 2
        self.assertEqual(len(w.validate_proposals({"proposals": [stale]}, changed)), 1)
        self.assertTrue(before["proposals"])

    def test_exact_evidence_and_method_references_required(self):
        state = completed_answers()
        valid = proposal()
        self.assertEqual(w.validate_proposals({"proposals": [valid]}, state)[0]["status"], "pending")
        bad_items = []
        wrong_quote = deepcopy(valid)
        wrong_quote["evidence"][0]["text"] = "This person is an experienced surgeon."
        bad_items.append(wrong_quote)
        wrong_ref = deepcopy(valid)
        wrong_ref["evidence"][0]["ref_id"] = "unreviewed-document"
        bad_items.append(wrong_ref)
        wrong_method = deepcopy(valid)
        wrong_method["method_ids"] = ["invented-chapter"]
        bad_items.append(wrong_method)
        wrong_type = deepcopy(valid)
        wrong_type["method_ids"] = [{}]
        bad_items.append(wrong_type)
        for invalid in bad_items:
            with self.subTest(invalid=invalid), self.assertRaises(CoachError):
                w.validate_proposals({"proposals": [invalid]}, state)

    def test_motives_require_roots_answers_not_just_resume(self):
        state = completed_answers(skipped={"roots_value", "roots_example", "roots_service"})
        invalid = proposal()
        card = w.personal_context(state)[0]
        invalid["evidence"] = [{"ref_id": card["id"], "revision": 1, "text": card["text"]}]
        with self.assertRaises(CoachError):
            w.validate_proposals({"proposals": [invalid]}, state)

    def test_future_goals_cannot_be_evidence_of_current_skills(self):
        state = completed_answers()
        invalid = proposal("ingredient", "ingredient_future", "I facilitate orientation sessions.")
        with self.assertRaises(CoachError):
            w.validate_proposals({"proposals": [invalid]}, state)
        invalid["evidence"].append({"ref_id": "ingredient_current", "revision": 1, "text": w.SAMPLE_ANSWERS["ingredient_current"]})
        with self.assertRaises(CoachError):
            w.validate_proposals({"proposals": [invalid]}, state)
        valid = proposal("future_ingredient", "ingredient_future", "I want to learn to facilitate orientation sessions.")
        self.assertEqual(w.validate_proposals({"proposals": [valid]}, state)[0]["kind"], "future_ingredient")

    def test_directions_require_prospective_answer_and_numbers_need_cited_support(self):
        state = completed_answers()
        with self.assertRaises(CoachError):
            w.validate_proposals({"proposals": [proposal("direction", "roots_value")]}, state)
        with self.assertRaises(CoachError):
            w.validate_proposals({"proposals": [proposal(wording="I helped 50 people feel welcome.")]}, state)
        self.assertEqual(w.validate_proposals({"proposals": []}, state), [])

    def test_explicit_own_words_preserves_long_answers_without_model(self):
        state = w.new_state("live", w.SAMPLE_EXPERIENCES)
        long_answer = "My own words. " * 80
        state = w.advance(state, long_answer)
        for step in w.STEPS[1:]:
            state = w.advance(state, "", skip=True)
        with patch("workshop._request_json") as call:
            result = w.build_own_words(state)
        call.assert_not_called()
        self.assertEqual(result["proposals"][0]["wording"], long_answer.strip())
        self.assertEqual(result["proposals"][0]["authorship"], "user_words")

    def test_review_requires_each_decision_and_marks_edited_wording(self):
        state = w.build_own_words(completed_answers())
        decisions = [{"id": item["id"], "decision": "accept"} for item in state["proposals"]]
        with self.assertRaises(w.WorkshopError):
            w.review(state, decisions[:-1])
        duplicate = deepcopy(decisions)
        duplicate[-1] = duplicate[0]
        with self.assertRaises(w.WorkshopError):
            w.review(state, duplicate)
        decisions[0].update(decision="edit", wording="I choose my own interpretation.")
        decisions[1]["decision"] = "reject"
        result = w.review(state, decisions)
        self.assertEqual(result["phase"], "complete")
        self.assertEqual(result["records"][0]["authorship"], "user_edited")
        self.assertIn("does not verify", result["records"][0]["evidence_note"])
        self.assertEqual(len(result["records"]), len(decisions) - 1)
        self.assertEqual(result["proposals"], [])
        self.assertTrue(state["proposals"])

    def test_rejected_ai_wording_never_survives_export(self):
        state = completed_answers()
        state.update(phase="review", proposals=w.validate_proposals({"proposals": [proposal(wording="A tentative special wording to reject.")]}, state))
        pending = w.export_state(state)
        self.assertEqual(pending["accepted"], [])
        self.assertEqual(pending["pending"][0]["status"], "pending")
        result = w.review(state, [{"id": state["proposals"][0]["id"], "decision": "reject"}])
        exported = w.export_state(result)
        self.assertNotIn("A tentative special wording", json.dumps(exported))
        self.assertEqual(exported["accepted"], [])
        self.assertEqual(exported["pending"], [])
        self.assertEqual(exported["decisions"][0]["decision"], "reject")

    def test_provider_receives_bounded_private_context_but_state_does_not(self):
        state = completed_answers()
        original = deepcopy(state)
        with patch("workshop._request_json", return_value={"proposals": [proposal()]}) as call:
            result = w.synthesize(state, packet(), {})
        self.assertEqual(state, original)
        self.assertEqual(result["phase"], "review")
        self.assertIn("Private source passage", call.call_args.args[1])
        self.assertEqual(call.call_args.kwargs["max_tokens"], 2400)
        self.assertNotIn("Private source passage", json.dumps(result))
        self.assertNotIn("Private source passage", json.dumps(w.export_state(result)))
        with patch("workshop._request_json", side_effect=CoachError("Retry")), self.assertRaises(CoachError):
            w.synthesize(state, packet(), {})
        self.assertEqual(state, original)

    def test_skipped_answers_constrain_generation_without_weakening_validation(self):
        state = completed_answers(skipped={"roots_example", "roots_service", "ingredient_current", "direction", "direction_why"})
        original = deepcopy(state)
        valid = [proposal(), proposal("future_ingredient", "ingredient_future", "I want to learn facilitation.")]
        with patch("workshop._request_json", return_value={"proposals": valid}) as call:
            result = w.synthesize(state, packet(), {})
        call.assert_called_once()
        prompt = call.call_args.args[1]
        rules = json.loads(prompt.split("SESSION EVIDENCE RULES: ", 1)[1].split(". Only propose kinds", 1)[0])
        self.assertEqual(set(rules), {"root", "future_ingredient", "theme"})
        self.assertEqual(rules["root"]["cite_at_least_one_of"], ["roots_value"])
        self.assertEqual(rules["future_ingredient"]["cite_at_least_one_of"], ["ingredient_future"])
        self.assertEqual([item["kind"] for item in result["proposals"]], ["root", "future_ingredient"])
        self.assertEqual(state, original)
        # Even if the model ignores the rules, reject rather than invent evidence or retry automatically.
        invalid = proposal("ingredient", "ingredient_future")
        with patch("workshop._request_json", return_value={"proposals": [invalid]}) as call:
            with self.assertRaises(CoachError):
                w.synthesize(state, packet(), {})
        call.assert_called_once()
        self.assertEqual(state, original)

    def test_packet_validation_fails_closed_and_discards_private_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            data = packet()
            data["private_notes"] = "NOT NEEDED BY MODEL"
            path.write_text(json.dumps(data))
            loaded = w.load_packet(path)
            self.assertNotIn("private_notes", loaded)
            self.assertNotIn("Private source passage", json.dumps(w.public_metadata()))
            for invalid in ({}, dict(data, method_id="unreviewed-v2"), dict(data, methods=data["methods"][:2])):
                path.write_text(json.dumps(invalid))
                with self.assertRaises(w.WorkshopError) as error:
                    w.load_packet(path)
                self.assertNotIn(str(path), str(error.exception))
            path.write_text("x" * 32001)
            with self.assertRaises(w.WorkshopError):
                w.load_packet(path)


if __name__ == "__main__":
    unittest.main()
