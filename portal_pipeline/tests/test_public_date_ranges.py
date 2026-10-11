"""Date range parsing: en dash tolerance without inventing or guessing dates. Fabricated sources only."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PROFILE_FIXTURE = Path(__file__).resolve().parent / "fixtures/synthetic_profile"
sys.path.insert(0, str(HERE))
from portal_profile import month, resolve_profile

EN, EM = "–", "—"
RESOLVED = [
    ("January 2020 to February 2021", "2020-01", "2021-02"),
    (f"January 2020 {EN} February 2021", "2020-01", "2021-02"),
    (f"Jan 2020{EN}Feb 2021", "2020-01", "2021-02"),
    (f"Jan 2020 {EN}Feb 2021", "2020-01", "2021-02"),
    (f"Jan 2020{EM}Feb 2021", "2020-01", "2021-02"),
    (f"Jan 2020 {EM} Feb 2021", "2020-01", "2021-02"),
    ("Jan 2020 - Feb 2021", "2020-01", "2021-02"),
    (f"  Sept 2020 {EN} Oct. 2021  ", "2020-09", "2021-10"),
    (f"JAN 2020 {EN} FEB 2021", "2020-01", "2021-02"),
]
# One readable side keeps its own fact; the unreadable side stays pending.
PARTIAL = [
    (f"Jan 2020 {EN} Present", "2020-01", None),
    (f"Jan 2020{EN}Current", "2020-01", None),
    (f"Jan 2020 {EN} ", "2020-01", None),
    (f"Smarch 2020 {EN} Feb 2021", None, "2021-02"),
]
PENDING = [
    (f"2019 {EN} 2021", None, None),
    ("Jan 2020-Feb 2021", None, None),
    (f"Jan 2020 {EN} Feb 2021 {EN} Mar 2022", None, None),
    (f"Feb 2021 {EN} Jan 2020", None, None),
    ("Unknown", None, None),
    ("", None, None),
]


class DateRangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(PROFILE_FIXTURE, self.root / "_Reference")

    def tearDown(self):
        self.temp.cleanup()

    def values(self, date_range):
        path = self.root / "_Reference" / "Resume_Content_Master.json"
        master = json.loads(path.read_text(encoding="utf-8"))
        master["experience"] = [{"company": "Synthetic Company", "location": "Example City", "dateRange": date_range, "roles": [{"title": "Synthetic Role"}]}]
        path.write_text(json.dumps(master), encoding="utf-8")
        values = resolve_profile(self.root)["values"]
        return (values.get("employment.0.start_date", {}).get("value"), values.get("employment.0.end_date", {}).get("value"))

    def test_ranges_with_dash_variants_resolve(self):
        for text, start, end in RESOLVED:
            with self.subTest(text=text):
                self.assertEqual(self.values(text), (start, end))

    def test_partially_readable_ranges_keep_only_the_readable_side(self):
        for text, start, end in PARTIAL:
            with self.subTest(text=text):
                self.assertEqual(self.values(text), (start, end))

    def test_unresolvable_ranges_stay_pending_and_nothing_is_guessed(self):
        for text, _, _ in PENDING:
            with self.subTest(text=text):
                self.assertEqual(self.values(text), (None, None))

    def test_month_parser(self):
        for text, expected in {"January 2020": "2020-01", "Jan 2020": "2020-01", "Sept 2020": "2020-09", "Sep. 2020": "2020-09",
                               "2020-01": None, "2020": None, "Present": None, "": None, "Smarch 2020": None}.items():
            with self.subTest(text=text):
                self.assertEqual(month(text), expected)


if __name__ == "__main__":
    unittest.main()
