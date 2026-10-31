import tempfile
import unittest
from pathlib import Path

import assist_api


class HistoryAnswerTest(unittest.TestCase):
    def test_education_and_certification_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = assist_api.AssistService(Path(tmp) / "d", Path(tmp) / "r", token="x" * 40)
            service.profile_path = Path(assist_api.DEFAULT_PROFILE)
            self.assertEqual(service.history({})["education"], 2)
            ask = lambda label, group, index: service.history_answer({"label": label, "row_group": group, "row_index": index})
            self.assertEqual(ask("School or University", "education", 0)["answer"], "Rutgers Business School")
            self.assertEqual(ask("Field of Study", "education", 0)["answer"], "Quantitative Finance")
            self.assertEqual(ask("Degree", "education", 1)["candidates"][1], "Bachelor's Degree")
            self.assertEqual(ask("Last Year Attended", "education", 0)["answer"], "2026")
            self.assertEqual(ask("Certification", "certification", 0)["answer"], "CFA Charterholder")
            self.assertIsNone(ask("Certification Number", "certification", 0))
            self.assertIsNone(ask("School", "education", 9))
            self.assertIsNone(service.history_answer({"label": "School"}))


if __name__ == "__main__":
    unittest.main()
