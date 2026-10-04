"""Prove that the real extension popup can be awaited without unsafe eval."""

import json
import re
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


EXTENSION = Path(__file__).resolve().parents[1] / "extension"


class ConfigHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/config" or self.headers.get("X-Portal-Token") != "synthetic-token":
            self.send_error(404)
            return
        time.sleep(0.25)
        payload = json.dumps({"status": "synthetic"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


class CspPopupWaitTests(unittest.TestCase):
    def test_locator_wait_observes_real_pairing_status(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ConfigHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as browser_profile, sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    browser_profile, channel="chromium", headless=True,
                    args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"],
                )
                try:
                    workers = context.service_workers
                    worker = workers[0] if workers else context.wait_for_event("serviceworker")
                    extension_id = worker.url.split("/")[2]
                    popup = context.new_page()
                    popup.goto(f"chrome-extension://{extension_id}/popup.html")
                    popup.locator("#server").fill(f"http://127.0.0.1:{server.server_port}")
                    popup.locator("#token").fill("synthetic-token")
                    popup.locator("#pair").click()
                    expect(popup.locator("#status")).to_have_text(re.compile(r"^Paired\."), timeout=30000)
                finally:
                    context.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
