"""Loaded-extension and Greenhouse browser trials use synthetic data only."""
import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from browser_test_support import BROWSER_CHANNEL, HERE, SyntheticBrowserTest, sync_playwright

# Trial configuration
PROFILE_FIXTURE = Path(__file__).resolve().parent / "fixtures/synthetic_profile"
RESULTS = HERE / "test-results"
HEADFUL = os.environ.get("PORTAL_TEST_HEADFUL") == "1"
PAIRING_TOKEN = "synthetic-browser-trial-token"
SESSION_ID = "a" * 32
ATTACHMENT_BYTES = b"Synthetic attachment bytes. Not a real resume or audited document."
GREENHOUSE_URL = "https://job-boards.greenhouse.io/synthetic/jobs/123"
ATTACHMENT = {"base64": base64.b64encode(ATTACHMENT_BYTES).decode(),
              "sha256": hashlib.sha256(ATTACHMENT_BYTES).hexdigest(),
              "name": "Synthetic_Resume.docx", "mime": "application/octet-stream"}

sys.path.insert(0, str(HERE))
from portal_profile import resolve_profile
from server import make_server


def save_screenshot(page, name):
    from PIL import Image, PngImagePlugin
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / name
    page.screenshot(path=str(path), full_page=True)
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Author", "Yazad Madan")
    with Image.open(path) as captured:
        captured.save(path, pnginfo=metadata)


class PublicExtensionTrial(unittest.TestCase):
    def test_loaded_extension_pair_review_selected_fill_and_upload(self):
        if sync_playwright is None:
            self.skipTest("Install requirements-dev.txt for the browser trial.")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(PROFILE_FIXTURE, root / "_Reference")
            current = {"id": SESSION_ID, "company": "Synthetic Employer", "role": "Synthetic Analyst",
                       "mode": "sandbox", "state": "built", "upload_reviewed": True}
            pipeline = SimpleNamespace(source=root, lock=threading.RLock(), templates=lambda: [],
                                       current=lambda: current,
                                       resume=lambda session_id, for_upload=False: ATTACHMENT_BYTES)
            server = make_server(pipeline, 0, PAIRING_TOKEN)
            url = f"http://127.0.0.1:{server.server_port}"
            current["url"] = url + "/fixture"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as playwright:
                    context = playwright.chromium.launch_persistent_context(str(root / "browser"),
                        channel=BROWSER_CHANNEL or "chromium", headless=not HEADFUL,
                        args=[f"--disable-extensions-except={HERE / 'extension'}", f"--load-extension={HERE / 'extension'}"],
                        viewport={"width": 1280, "height": 900})
                    try:
                        workers = context.service_workers
                        worker = workers[0] if workers else context.wait_for_event("serviceworker")
                        extension_id = worker.url.split("/")[2]
                        allowed_urls = (url + "/", f"chrome-extension://{extension_id}/")
                        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(allowed_urls) else route.abort())
                        def isolated_fixture(route):
                            response = route.fetch()
                            markup = response.text()
                            for script in ["fixture-adapter.js", "fixture-engine.js", "fixture-panel.js"]:
                                markup = markup.replace(f'<script src="/{script}"></script>', "")
                            route.fulfill(response=response, body=markup)
                        context.route(url + "/fixture", isolated_fixture)
                        page = context.new_page()
                        page.goto(url + "/fixture")
                        popup = context.new_page()
                        popup.goto(f"chrome-extension://{extension_id}/popup.html")
                        popup.locator("#server").fill(url)
                        popup.locator("#token").fill(PAIRING_TOKEN)
                        popup.locator("#pair").click()
                        try:
                            popup.locator("#status").filter(has_text="Paired.").wait_for(timeout=10000)
                        except Exception as error:
                            save_screenshot(popup, "synthetic-pairing-failure.png")
                            raise AssertionError("Synthetic pairing status: " + popup.locator("#status").inner_text()) from error
                        tab_id = popup.evaluate("async target => (await chrome.tabs.query({})).find(tab => tab.url === target).id", url + "/fixture")
                        review = context.new_page()
                        review.goto(f"chrome-extension://{extension_id}/review.html?tab={tab_id}")
                        host = review.locator("#portal-panel-host")
                        host.get_by_role("checkbox", name="Select Last name", exact=True).wait_for()
                        for label in ["Last name", "Phone", "Do you require sponsorship now?", "Will you require sponsorship in the future?"]:
                            host.get_by_role("checkbox", name="Select " + label, exact=True).check()
                        host.get_by_role("checkbox", name="Select Are you willing to relocate?", exact=True).check()
                        host.get_by_role("combobox", name="Answer Are you willing to relocate?", exact=True).select_option(label="Yes")
                        host.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
                        host.get_by_role("button", name="Fill selected fields", exact=True).click()
                        host.get_by_text("4 filled, 1 preserved, 0 need attention.", exact=False).wait_for()
                        self.assertEqual(page.locator("#last").input_value(), "Candidate")
                        self.assertEqual(page.locator("#first").input_value(), "")
                        self.assertEqual(page.locator("#email").input_value(), "")
                        self.assertEqual(page.locator("#authorized").input_value(), "")
                        self.assertEqual(page.locator("#phone").input_value(), "Keep this existing value")
                        self.assertEqual(page.locator("#now").input_value(), "0")
                        self.assertEqual(page.locator("#future").input_value(), "1")
                        self.assertEqual(page.locator("#custom-relocation").get_attribute("aria-valuetext"), "Yes")
                        self.assertFalse(page.evaluate("Boolean(globalThis.PortalEngine)"))
                        self.assertEqual(page.locator("#portal-panel-host").count(), 0)
                        save_screenshot(review, "synthetic-extension-review.png")
                        save_screenshot(page, "synthetic-workday-contact.png")
                        page.locator("#next-one").click()
                        review.locator("#rescan").click()
                        host.get_by_role("checkbox", name="Select Resume", exact=True).wait_for()
                        host.get_by_role("checkbox", name="Select Resume", exact=True).check()
                        host.get_by_role("checkbox", name="This page belongs to the selected posting", exact=True).check()
                        host.get_by_role("button", name="Fill selected fields", exact=True).click()
                        host.get_by_text("1 filled, 0 preserved, 0 need attention.", exact=False).wait_for()
                        self.assertEqual(page.locator("#resume").evaluate("node => node.files[0].name"), "Yazad_Madan.docx")
                        self.assertEqual(page.locator("#cover").evaluate("node => node.files.length"), 0)
                        self.assertEqual(page.locator("#why").input_value(), "")
                        save_screenshot(page, "synthetic-workday-upload.png")
                        page.locator("#next-two").click()
                        review.locator("#rescan").click()
                        host.get_by_role("checkbox", name="Select Signature", exact=True).wait_for()
                        self.assertTrue(host.get_by_role("checkbox", name="Select Signature", exact=True).is_disabled())
                        self.assertFalse(page.locator("#attestation").is_checked())
                        self.assertEqual(page.locator("#signature").input_value(), "")
                        self.assertEqual(page.locator("#submit-count").text_content(), "Submit clicks: 0")
                        inspect = context.new_page()
                        inspect.goto(f"chrome-extension://{extension_id}/review.html?tab={tab_id}&mode=inspect")
                        inspect.get_by_text("No application fields found.", exact=False).wait_for()
                        for command in ["portal-scan", "portal-fill"]:
                            rejected = inspect.evaluate("async ({tabId, type}) => chrome.tabs.sendMessage(tabId, {type, profile:{values:{}}, selections:[]})", {"tabId": tab_id, "type": command})
                            self.assertFalse(rejected["ok"])
                            self.assertIn("Inspection mode", rejected["error"])
                    finally:
                        context.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class PublicGreenhouseTrial(SyntheticBrowserTest):
    def test_synthetic_greenhouse_selected_fields_hidden_upload_and_refusals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(PROFILE_FIXTURE, root / "_Reference")
            profile = resolve_profile(root)
        self.open_markup((HERE / "fixtures/greenhouse.html").read_text(encoding="utf-8"), GREENHOUSE_URL)
        fields = self.scan(profile["values"])
        selected = [field for field in fields if field["structure"]["dom_id"] in {"first_name", "resume"}]
        self.assertEqual(len(selected), 2)
        result = self.fill([{"id": field["id"], "value": field["proposal"]} for field in selected], {"attachment": ATTACHMENT})
        self.assertEqual([item["status"] for item in result], ["filled", "filled"])
        self.assertEqual(self.page.locator("#first_name").input_value(), "Synthetic")
        self.assertEqual(self.page.locator("#last_name").input_value(), "")
        self.assertEqual(self.page.locator("#newsletter").input_value(), "KEEP NEWSLETTER")
        self.assertEqual(self.page.locator("#required-shadow").input_value(), "KEEP SHADOW")
        self.assertEqual(self.page.locator("#phone").input_value(), "KEEP PHONE")
        self.assertEqual(self.page.locator("#cover_letter").evaluate("node => node.files.length"), 0)
        self.assertEqual(self.page.locator("#transgender").input_value(), "")
        self.assertEqual(self.page.locator("#survey-education").input_value(), "")
        country = next(field for field in fields if field["structure"]["dom_id"] == "country")
        refused = self.fill([{"id": country["id"], "value": "Synthetic country"}])
        self.assertEqual(refused[0]["status"], "failed")
        self.assertEqual(self.page.locator("#country").input_value(), "")
        self.assertEqual(self.page.locator("#compound").input_value(), "")
        self.assertEqual(self.page.locator("#signature").input_value(), "")
        self.assertEqual(self.page.evaluate("submitAttempts"), 0)
        save_screenshot(self.page, "synthetic-greenhouse-trial.png")


if __name__ == "__main__":
    unittest.main()
