"""Synthetic tests for long-form evidence and validation."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from longform import check_numbers, count_chars, evidence_for, fit


class LongformTests(unittest.TestCase):
    def test_count_chars_matches_js(self):
        cases = {"plain": 5, "A\U0001f600B": 4, "a\nb": 4,
                 "a\r\nb": 4, "a\rb": 4, "\U0001f600\n\U0001f600": 6}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(count_chars(value), expected)
        if shutil.which("node"):
            script = ("const cases = JSON.parse(process.argv[1]); "
                      "process.stdout.write(JSON.stringify(cases.map(s => s.replace(/\\r\\n|\\r|\\n/g, '\\r\\n').length))); ")
            result = subprocess.run(["node", "-e", script, json.dumps(list(cases))],
                                    check=True, capture_output=True, text=True)
            self.assertEqual([count_chars(value) for value in cases], json.loads(result.stdout))

    def test_unsupported_number_flagged(self):
        evidence = [{"text": "Measured 1,000 requests at 8.5% in 2024, down from -2.", "source": "synthetic"}]
        self.assertEqual(check_numbers("Handled 1000 requests; 8.5 percent in 2024.", evidence), [])
        self.assertEqual(check_numbers("Handled 1,001 requests, 8.6%, and 2025.", evidence),
                         ["1,001", "8.6%", "2025"])
        self.assertEqual(check_numbers("Grew 2 while evidence says -2.", evidence), ["2"])
        self.assertEqual(check_numbers("Grew -8.5% while evidence says 8.5%.", evidence), ["-8.5%"])
        self.assertEqual(check_numbers("Reached 8.5% after evidence gives 8.5 without percent.",
                                       [{"text": "Measured 8.5", "source": "synthetic"}]), ["8.5%"])
        self.assertEqual(check_numbers("In 2024-2025, shipped twice.", evidence), ["2025"])
        self.assertEqual(check_numbers("Made 1.0 and 1.0 changes.", evidence), ["1.0"])
        self.assertEqual(check_numbers("Scaled 1e3 and reduced by 1/2.", evidence), ["1e3", "1/2"])
        self.assertEqual(check_numbers("Scaled 1e3 and reduced by 1/2.",
                                       [{"text": "Observed 1e3 and 1/2", "source": "synthetic"}]), [])
        bare = [{"text": "Observed 5 and 3 and 999", "source": "synthetic"}]
        self.assertEqual(check_numbers("Reached 5k, 5M, 3x, .5%, 5 million, and v999.", bare),
                         ["5k", "5M", "3x", ".5%", "5 million", "v999"])
        exact = [{"text": "Observed 5k, 5M, 3x, .5 percent, 5 million, and v999.", "source": "synthetic"}]
        self.assertEqual(check_numbers("Reached 5k, 5M, 3x, .5%, 5 million, and v999.", exact), [])
        self.assertEqual(check_numbers("Reached 5 million", [{"text": "Observed 5M", "source": "synthetic"}]),
                         ["5 million"])

    def test_draft_over_limit_blocked(self):
        self.assertEqual(fit("A\U0001f600\nB", 5), {"ok": False, "count": 6, "limit": 5})
        self.assertEqual(fit("A\U0001f600\nB", 6), {"ok": True, "count": 6, "limit": 6})
        for limit in (None, 0, -1, True, "6"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                fit("draft", limit)

    def test_evidence_sources_only_from_allowed_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "_Reference"
            reference.mkdir()
            (reference / "Application_Boilerplate.md").write_text(
                "## Standard Boilerplate Answers\n- Salary: 999999\n\n"
                "## Role Descriptions\n### Synthetic Analyst\n"
                "Validated 1,000 synthetic records.\n"
                "[TODO: unconfirmed 777]\n\n---\n\n"
                "## Why Us\n- The synthetic mission matches my research on 2024 fixtures.\n"
                "- TBD 888\n\n## Private Notes\nOther figure 555.\n", encoding="utf-8")
            project = evidence_for("Describe a project", root)
            why = evidence_for("Why this company?", root)
            why_work = evidence_for("Why do you want to work here?", root)
            self.assertTrue(project)
            self.assertTrue(why)
            self.assertTrue(all("#Role Descriptions:L" in item["source"] for item in project))
            self.assertTrue(all("#Why Us:L" in item["source"] for item in why))
            self.assertEqual(why_work, why)
            self.assertIn("1,000", " ".join(item["text"] for item in project))
            all_text = " ".join(item["text"] for item in project + why)
            for forbidden in ("999999", "777", "888", "555"):
                self.assertNotIn(forbidden, all_text)
            self.assertEqual(evidence_for("", root), [])

    def test_missing_evidence_stays_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(evidence_for("Describe a project", Path(temporary)), [])
        self.assertEqual(check_numbers("Improved 5%", []), ["5%"])


if __name__ == "__main__":
    unittest.main()
