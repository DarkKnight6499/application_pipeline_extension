"""Answer memory matches exact normalized questions only and never stores protected questions."""
import sys
import tempfile
import unittest

from browser_test_support import HERE

sys.path.insert(0, str(HERE))
import answer_memory as memory


class AnswerMemoryTests(unittest.TestCase):
    def fresh(self):
        return {"schema_version": 1, "answers": {}}

    def test_exact_match_ignores_case_and_punctuation(self):
        data = self.fresh()
        self.assertTrue(memory.remember(data, "Are you legally authorized to work in the US?", "Yes"))
        self.assertEqual(memory.lookup(data, "are you legally authorized to work in the us"), "Yes")

    def test_reworded_question_does_not_match(self):
        data = self.fresh()
        memory.remember(data, "Are you legally authorized to work in the US?", "Yes")
        self.assertIsNone(memory.lookup(data, "Do you have legal authorization to work in the US?"))

    def test_protected_questions_are_refused(self):
        data = self.fresh()
        for label in ("I certify this is true", "Password", "I agree to the privacy policy", "Signature"):
            self.assertFalse(memory.remember(data, label, "x"), label)
        self.assertEqual(data["answers"], {})

    def test_demographic_self_id_answers_are_stored(self):
        data = self.fresh()
        for label in ("What is your gender?", "Do you have a disability?", "Are you a veteran?", "What is your ethnicity?"):
            self.assertTrue(memory.remember(data, label, "No"), label)

    def test_empty_and_oversized_are_refused(self):
        data = self.fresh()
        self.assertFalse(memory.remember(data, "", "Yes"))
        self.assertFalse(memory.remember(data, "Q", " "))
        self.assertFalse(memory.remember(data, "Q", "x" * 2001))

    def test_gaps_lists_unanswered_unprotected_once(self):
        data = self.fresh()
        memory.remember(data, "Notice period", "2 weeks")
        fields = [{"label": "Notice period"}, {"label": "Why us?"}, {"label": "why us"}, {"label": "I agree to the terms"}, {"label": ""}]
        self.assertEqual(memory.gaps(data, fields), ["Why us?"])

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            data = memory.load_memory(folder)
            memory.remember(data, "Notice period", "2 weeks")
            memory.save_memory(data, folder)
            self.assertEqual(memory.lookup(memory.load_memory(folder), "Notice period"), "2 weeks")


if __name__ == "__main__":
    unittest.main()
