"""Author: Yazad Madan. Repeating-section labels are reported as REPEATED and never promoted."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import assist_api
import page_questions
import questions_sort

HOST = "example.myworkdayjobs.com"


def pair(label, answer):
    return {"label": label, "answer": answer, "source": "filled", "type": "text"}


class RepeatedTests(unittest.TestCase):
    def test_same_label_twice_on_one_page_and_indexed_labels_are_repeated(self):
        with tempfile.TemporaryDirectory() as temp:
            service = assist_api.AssistService(Path(temp) / "data", Path(temp) / "ref", token="t")
            page_questions.capture(service, {"host": HOST, "url": "https://" + HOST + "/a", "company_hint": "Example",
                "pairs": [pair("Job Title*", "Analyst"), pair("Job Title*", "Manager"),
                          pair("Work Experience 1: I currently work here", "No"), pair("City*", "Harrison")]})
            report = questions_sort.report(service)
            self.assertEqual(sorted(g["label"] for g in report["REPEATED"]),
                             ["Job Title*", "Work Experience 1: I currently work here"])
            self.assertEqual([g["label"] for g in report["SINGLE"]], ["City*"])
            self.assertEqual(report["CONFLICT"], [])


if __name__ == "__main__":
    unittest.main()
