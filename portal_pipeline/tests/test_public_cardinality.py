"""Replay existing browser assertions on the public fixture with fabricated facts."""
import ast
import re
from types import MethodType

from browser_test_support import HERE, SYNTHETIC_URL, SyntheticBrowserTest

# Synthetic regression configuration
BROWSER_TEST_FILE = HERE / "tests/test_browser.py"
FIXTURE_HTML = HERE / "fixtures/workday.html"
FIXTURE_SCRIPT = HERE / "fixtures/workday.js"
ROLE_COUNT = 5
HISTORY_PROPERTIES = ("company", "title", "start_date", "end_date")
OMITTED_SCAN_SURVIVORS = {"start-2", "end-4"}
EXPECTED_RESULT_COUNT = ROLE_COUNT * len(HISTORY_PROPERTIES)
METHOD_NAMES = {"scan", "history_bindings", "fill_keys",
                "test_repeated_employment_dates_and_manual_next",
                "test_submission_attestation_and_signature_are_untouched"}
SYNTHETIC_VALUES = {
    f"employment.{index}.{name}": {"value": value, "source": "Fabricated cardinality fixture"}
    for index in range(ROLE_COUNT)
    for name, value in {"company": f"Synthetic Company {index}", "title": f"Synthetic Role {index}",
                        "start_date": "2023-08" if index == 2 else "2021-01",
                        "end_date": "2022-05" if index == 4 else "2024-01"}.items()
}


def existing_assertions():
    tree = ast.parse(BROWSER_TEST_FILE.read_text(encoding="utf-8"))
    test_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BrowserTests")
    methods = [node for node in test_class.body if isinstance(node, ast.FunctionDef) and node.name in METHOD_NAMES]
    namespace = {}
    # Compile only target methods, avoiding private-source imports and integration setup.
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(BROWSER_TEST_FILE), "exec"), namespace)
    return namespace


class PublicCardinalityTests(SyntheticBrowserTest):
    def setUp(self):
        super().setUp()
        markup = re.sub(r'<script\b[^>]*>.*?</script>', '', FIXTURE_HTML.read_text(encoding="utf-8"), flags=re.DOTALL)
        self.context.route(SYNTHETIC_URL, lambda route: route.fulfill(content_type="text/html", body=markup))
        self.page.goto(SYNTHETIC_URL)
        for script in ("adapters/aria-listbox.js", "adapters/greenhouse.js", "adapters/greenhouse-select.js", "classifier.js", "engine.js"):
            self.page.add_script_tag(path=str(HERE / "extension" / script))
        self.page.add_script_tag(path=str(FIXTURE_SCRIPT))
        self.profile = {"values": SYNTHETIC_VALUES}
        self.methods = existing_assertions()
        for name in ("scan", "history_bindings", "fill_keys"):
            setattr(self, name, MethodType(self.methods[name], self))

    def test_empty_protected_scan_mutant_is_rejected(self):
        self.scan = lambda bindings=None: []
        with self.assertRaises(AssertionError):
            self.methods["test_submission_attestation_and_signature_are_untouched"](self)
        self.assertFalse(self.page.locator("#attestation").is_checked())
        self.assertEqual(self.page.locator("#signature").input_value(), "")
        self.assertEqual(self.page.locator("#submit-count").text_content(), "Submit clicks: 0")

    def test_partial_history_scan_mutant_is_rejected(self):
        original_scan = self.scan
        # Bind all five rows before simulating loss of most discovered fields.
        self.page.locator("#next-one").click()
        bindings = self.methods["history_bindings"](self, "employment")
        self.page.evaluate("step(1)")
        self.history_bindings = lambda group: bindings
        self.scan = lambda bindings=None: [field for field in original_scan(bindings)
                                          if field["structure"]["dom_id"] in OMITTED_SCAN_SURVIVORS]
        with self.assertRaises(AssertionError):
            self.methods["test_repeated_employment_dates_and_manual_next"](self)
        self.assertEqual(self.page.locator("#submit-count").text_content(), "Submit clicks: 0")

    def test_truncated_history_result_mutant_is_rejected(self):
        original_fill = self.fill_keys

        def truncated_fill(keys, bindings=None, **options):
            result = original_fill(keys, bindings, **options)
            self.assertEqual(len(result), EXPECTED_RESULT_COUNT)
            return result[:2]

        self.fill_keys = truncated_fill
        with self.assertRaises(AssertionError):
            self.methods["test_repeated_employment_dates_and_manual_next"](self)

    def test_unmutated_fixture_satisfies_existing_assertions(self):
        self.methods["test_repeated_employment_dates_and_manual_next"](self)
        self.page.evaluate("step(1)")
        self.methods["test_submission_attestation_and_signature_are_untouched"](self)
