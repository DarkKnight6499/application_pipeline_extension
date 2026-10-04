"""Replay recorded synthetic portal pages through the adapter interface with expected counts."""
import json
import unittest

from replay_support import (MANIFEST, PAGES, ReplayBrowserTest, compare, drop_label, duplicate_first_input,
                            load_cases)

# Replay test configuration
DRIFT_CASE = "generic_page_1"
DRIFT_LABEL = "First name"
REQUIRED_CASE_KEYS = {"name", "portal", "adapter", "pages", "url", "expect"}
REQUIRED_EXPECT_KEYS = {"fields", "required", "keys", "human_gate", "final_review", "next_kind"}
REQUIRED_PORTALS = {"generic", "greenhouse", "workday"}


class PublicReplayTests(ReplayBrowserTest):
    def case(self, name):
        return next(case for case in load_cases() if case["name"] == name)

    def test_replay_manifest_valid(self):
        cases = load_cases()
        self.assertEqual(len({case["name"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertTrue(REQUIRED_CASE_KEYS <= set(case))
                self.assertEqual(set(case["expect"]), REQUIRED_EXPECT_KEYS)
                self.assertTrue(case["pages"])
                for page in case["pages"]:
                    self.assertTrue((PAGES / page).is_file(), page)
        self.assertTrue(REQUIRED_PORTALS <= {case["portal"] for case in cases})
        self.assertTrue(any(case["expect"]["human_gate"] == "captcha" for case in cases))
        self.assertTrue(any(case.get("untouched") for case in cases))
        self.assertNotIn("\u2014", MANIFEST.read_text(encoding="utf-8"))

    def test_replay_generic_expectations(self):
        for case in load_cases():
            for page in case["pages"]:
                with self.subTest(case=case["name"], page=page):
                    observed = self.replay(case, (PAGES / page).read_text(encoding="utf-8"))
                    self.assertEqual(compare(case, observed), [])
                    self.assertEqual(observed["adapter"], case["adapter"])

    def test_replay_detects_label_drift(self):
        case = self.case(DRIFT_CASE)
        html = (PAGES / case["pages"][0]).read_text(encoding="utf-8")
        self.assertEqual(compare(case, self.replay(case, html)), [])
        self.assertNotEqual(html, drop_label(html, DRIFT_LABEL))
        self.assertTrue(compare(case, self.replay(case, drop_label(html, DRIFT_LABEL))))
        self.assertNotEqual(html, duplicate_first_input(html))
        self.assertTrue(compare(case, self.replay(case, duplicate_first_input(html))))

    def test_replay_submit_counter_zero(self):
        for case in load_cases():
            with self.subTest(case=case["name"]):
                observed = self.replay(case, (PAGES / case["pages"][-1]).read_text(encoding="utf-8"))
                self.assertEqual(observed["submit_counts"], [0, 0, 0])
                self.assertNotIn("SYNTHETIC_SECRET", json.dumps(observed))


if __name__ == "__main__":
    unittest.main()
