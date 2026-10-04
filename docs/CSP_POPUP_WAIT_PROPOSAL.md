---
author: Yazad Madan
---

# Popup pairing test wait under extension CSP

The inherited `test_real_extension_pairs_and_injects_on_user_action` uses
`popup.wait_for_function("document.getElementById('status').textContent.startsWith('Paired.')")`
on `chrome-extension://.../popup.html`. The observed failure stack shows
Playwright's function wait rejected by the extension Content Security Policy
with an `unsafe-eval` error. The popup sets the correct status in `popup.js`
after a successful `/api/config` response. Another inherited popup function
wait has the same CSP exposure.

Yazad approved the following inherited test changes on October 4, 2026. Both waits are now implemented; production CSP remains unchanged:

```diff
 import json
+import re
 ...
-from playwright.sync_api import sync_playwright
+from playwright.sync_api import expect, sync_playwright
 ...
-                popup.wait_for_function("document.getElementById('status').textContent.startsWith('Paired.')")
+                expect(popup.locator("#status")).to_have_text(re.compile(r"^Paired\."), timeout=30000)
 ...
-                popup.wait_for_function("document.getElementById('status').textContent.includes('limited to Workday')")
+                expect(popup.locator("#status")).to_contain_text("limited to Workday", timeout=30000)
```

The regular expression preserves the pairing prefix condition. The second
assertion preserves the substring condition. Both keep the existing 30-second
wait limit. Playwright's locator assertions poll element text without
evaluating the test's JavaScript strings in the extension page. They do not
change production CSP or pairing behavior.

`test_csp_popup_wait.py` loads the real extension, pairs it against a local
synthetic `/api/config` server with a delayed response, and passes with the
proposed locator assertion. It uses no candidate data or employer page.
