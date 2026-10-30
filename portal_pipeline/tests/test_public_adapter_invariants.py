"""Safety invariants across every adapter, checked statically and in one synthetic page."""
import json
import re
import unittest

from browser_test_support import HERE, SyntheticBrowserTest

EXTENSION = HERE / "extension"
ADAPTERS = EXTENSION / "adapters"
ROUTED = {"workday", "greenhouse", "phenom"}
UNROUTED = {"oracle", "ashby", "lever", "eightfold", "successfactors", "taleo", "smartrecruiters", "brassring", "icims", "fallback"}
FRAME_FILL = {"icims"}
ANSWER_SHEET_ONLY = {"oracle", "ashby", "smartrecruiters", "brassring", "fallback"}
# Unrouted adapters stay out of the unconditional injection lists; only these two are injected on purpose.
INJECTED_ON_PURPOSE = {"fallback.js": "popup.js review.js", "icims.js": "review.js"}
FORBIDDEN_IN_ADAPTERS = re.compile(r"\.submit\s*\(|requestSubmit|type\s*=\s*[\"']submit[\"'].*\.click|\.click\s*\(\s*\)\s*;?\s*//\s*submit", re.I)


class PublicAdapterInvariantTests(SyntheticBrowserTest):
    def load_all(self):
        self.open_markup("<h1>Synthetic</h1>")
        for name in ("generic", "workday", "aria-listbox", "greenhouse", "greenhouse-select", "phenom", "oracle", "ashby",
                     "lever", "eightfold", "successfactors", "taleo", "smartrecruiters", "brassring", "icims", "fallback"):
            self.page.add_script_tag(path=str(ADAPTERS / f"{name}.js"))
        return {item["id"]: item for item in self.page.evaluate("PortalAdapters.list()")}

    def test_every_adapter_file_is_classified(self):
        files = {path.stem for path in ADAPTERS.glob("*.js")}
        helpers = {"registry", "generic", "aria-listbox", "greenhouse-select"}
        self.assertEqual(files - helpers, ROUTED | UNROUTED, "Classify the new adapter in this test before adding it.")

    def test_routing_matches_classification(self):
        listed = self.load_all()
        for name in ROUTED:
            with self.subTest(name=name):
                self.assertTrue(listed[name]["hosts"], name)
        for name in UNROUTED:
            with self.subTest(name=name):
                self.assertEqual(listed[name]["hosts"], [], name)
        for name in ANSWER_SHEET_ONLY:
            with self.subTest(name=name):
                self.assertEqual(listed[name]["mode"], "answer_sheet_only")

    def test_only_expected_adapters_are_frame_fill(self):
        self.load_all()
        self.assertTrue(self.page.evaluate("PortalIcimsAdapter.frameFill === true"))
        sources = {p.stem for p in ADAPTERS.glob("*.js") if "frameFill" in p.read_text(encoding="utf-8")}
        self.assertEqual(sources, FRAME_FILL | set())

    def test_answer_sheet_adapters_declare_refusing_writers(self):
        for name in ANSWER_SHEET_ONLY:
            text = (ADAPTERS / f"{name}.js").read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertRegex(text, r"fill:\s*refuse")
                self.assertRegex(text, r"upload:\s*refuse")
                self.assertIn('mode: "answer_sheet_only"', text)

    def test_no_adapter_source_submits_or_signs(self):
        for path in ADAPTERS.glob("*.js"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIsNone(FORBIDDEN_IN_ADAPTERS.search(text))
                self.assertNotIn("form.submit", text)

    def test_manifest_permissions_unchanged(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["permissions"], ["activeTab", "scripting", "storage", "sidePanel"])
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1/*"])
        self.assertEqual(len(manifest["content_scripts"]), 1)
        self.assertEqual(manifest["content_scripts"][0]["js"], ["assist-content.js"])
        self.assertNotIn("<all_urls>", json.dumps(manifest))

    def test_unrouted_adapters_not_in_unconditional_injection_lists(self):
        for name in ("popup.js", "review.js"):
            text = (EXTENSION / name).read_text(encoding="utf-8")
            for file_name in {f"{n}.js" for n in UNROUTED}:
                with self.subTest(script=name, adapter=file_name):
                    allowed = file_name in INJECTED_ON_PURPOSE and name in INJECTED_ON_PURPOSE[file_name].split()
                    self.assertEqual(f"adapters/{file_name}" in text, allowed)


if __name__ == "__main__":
    unittest.main()
