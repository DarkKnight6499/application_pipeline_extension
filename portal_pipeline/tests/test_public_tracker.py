"""Tracker joins use fabricated workbooks and exact named application IDs."""
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

# Synthetic tracker configuration
HERE = Path(__file__).resolve().parents[1]
AUTHOR = "Yazad Madan"
TRACKER_FILENAME = "Applications.xlsx"
SELECTED_ID = 701
OTHER_ID = 702
SYNTHETIC_URL = "https://example.invalid/role/701"
sys.path.insert(0, str(HERE))
from audited_import import tracker_context

APPLICATION_ID_COLUMN = "Application ID"
COMPANY_COLUMN = "Company"
ROLE_COLUMN = "Role Title"
LINK_COLUMN = "Link"
STATUS_COLUMN = "Status"
REQUIRED_COLUMNS = [APPLICATION_ID_COLUMN, COMPANY_COLUMN, ROLE_COLUMN, LINK_COLUMN, STATUS_COLUMN]
SELECTED_ROW = {APPLICATION_ID_COLUMN: SELECTED_ID, COMPANY_COLUMN: "Synthetic Employer", ROLE_COLUMN: "Synthetic Role",
                LINK_COLUMN: SYNTHETIC_URL, STATUS_COLUMN: "To Apply"}


class PublicTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_tracker(self, columns, rows):
        workbook = Workbook()
        workbook.properties.creator = AUTHOR
        workbook.properties.lastModifiedBy = AUTHOR
        workbook.active.append(columns)
        for row in rows:
            workbook.active.append(row)
        workbook.save(self.root / TRACKER_FILENAME)
        workbook.close()

    def test_duplicate_required_headers_are_rejected(self):
        for column in REQUIRED_COLUMNS:
            with self.subTest(column=column):
                first_row = {**SELECTED_ROW, STATUS_COLUMN: "Applied"} if column == STATUS_COLUMN else SELECTED_ROW
                conflicting = ("New" if column == STATUS_COLUMN else OTHER_ID if column == APPLICATION_ID_COLUMN
                               else "https://example.invalid/wrong-posting" if column == LINK_COLUMN else "Conflicting context")
                self.write_tracker(REQUIRED_COLUMNS + [column], [[first_row[name] for name in REQUIRED_COLUMNS] + [conflicting]])
                with self.assertRaises(ValueError):
                    tracker_context(self.root, SELECTED_ID)

    def test_reordered_columns_and_rows_preserve_exact_id_join(self):
        other = {**SELECTED_ROW, APPLICATION_ID_COLUMN: OTHER_ID, LINK_COLUMN: "https://example.invalid/role/702"}
        columns = list(reversed(REQUIRED_COLUMNS))
        self.write_tracker(columns, [[row[name] for name in columns] for row in (other, SELECTED_ROW)])
        context = tracker_context(self.root, SELECTED_ID)
        self.assertEqual(context, {"application_id": SELECTED_ID, "company": SELECTED_ROW[COMPANY_COLUMN],
                         "role": SELECTED_ROW[ROLE_COLUMN], "url": SYNTHETIC_URL, "tracker_status": "To Apply"})

    def test_missing_required_headers_are_rejected(self):
        for missing in REQUIRED_COLUMNS:
            with self.subTest(missing=missing):
                columns = [name for name in REQUIRED_COLUMNS if name != missing]
                self.write_tracker(columns, [[SELECTED_ROW[name] for name in columns]])
                with self.assertRaisesRegex(ValueError, "missing required"):
                    tracker_context(self.root, SELECTED_ID)

    def test_duplicate_ids_and_applied_status_remain_rejected(self):
        for rows in ([SELECTED_ROW, SELECTED_ROW], [{**SELECTED_ROW, STATUS_COLUMN: "Applied"}]):
            with self.subTest(rows=rows):
                self.write_tracker(REQUIRED_COLUMNS, [[row[name] for name in REQUIRED_COLUMNS] for row in rows])
                with self.assertRaises(ValueError):
                    tracker_context(self.root, SELECTED_ID)

    def test_empty_tracker_has_clear_missing_header_error(self):
        self.write_tracker([], [])
        with self.assertRaisesRegex(ValueError, "missing required"):
            tracker_context(self.root, SELECTED_ID)
