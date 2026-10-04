"""P7 progression guards on fabricated pages; the submit counter must stay zero throughout."""
import base64
import hashlib

from browser_test_support import HERE, SyntheticBrowserTest

# Synthetic configuration
PROGRESS_SCRIPT = HERE / "extension/progress.js"
ATTACHMENT_BYTES = b"\x01\x02\x03"
ATTACHMENT = {"base64": base64.b64encode(ATTACHMENT_BYTES).decode(), "sha256": hashlib.sha256(ATTACHMENT_BYTES).hexdigest(),
              "name": "Synthetic_Resume.docx", "mime": "application/octet-stream"}
COUNT_CLICKS = '<script>window.nextClicks = 0; document.addEventListener("click", e => {if (e.target.closest("#go")) nextClicks++;}, true);</script>'


class ProgressTests(SyntheticBrowserTest):
    def open_page(self, markup):
        self.open_markup(markup)
        self.page.evaluate("document.getElementById('guard-submit').hidden = true; document.getElementById('guard-untouched').parentElement.hidden = true")
        self.page.add_script_tag(path=str(PROGRESS_SCRIPT))

    def sweep(self):
        return self.page.evaluate("async () => PortalProgress.requiredSweep(PortalAdapters.forLocation(location.href))")

    def enable_next(self):
        self.page.evaluate("PortalProgress.settings.allowGuardedNext = true")

    def guarded(self):
        return self.page.evaluate("async () => PortalProgress.guardedNext(PortalAdapters.forLocation(location.href))")

    def test_sweep_finds_hidden_block_required_after_reveal(self):
        self.open_page('<label>Name<input id="n" required></label><div id="more" hidden><label>City<input id="c" required></label></div>'
                       '<script>setTimeout(() => {more.hidden = false;}, 30);</script>')
        result = self.sweep()
        self.assertEqual(sorted(item["label"] for item in result["missing"]), ["City", "Name"])
        self.assertEqual(result["checked"], 2)

    def test_placeholder_select_is_missing(self):
        self.open_page('<label>Country<select id="s" required><option value="">Select one</option><option>USA</option></select></label>'
                       '<label>Mode<select id="m" required><option>Pick</option><option>Remote</option></select></label>'
                       '<label>Shift<select id="x" required><option value="">Choose</option><option>Day</option></select></label>')
        self.page.locator("#m").select_option("Remote")
        reasons = {item["label"]: item["reason"] for item in self.sweep()["missing"]}
        self.assertEqual(reasons, {"Country": "placeholder_selected", "Shift": "placeholder_selected"})

    def test_unchecked_required_checkbox_missing(self):
        self.open_page('<label>Contact me<input id="k" type="checkbox" required></label><label>Name *<input id="n" value="Ada"></label>')
        result = self.sweep()
        self.assertEqual([(item["label"], item["reason"]) for item in result["missing"]], [("Contact me", "unchecked_required")])
        self.assertEqual(result["checked"], 2)

    def test_stall_after_two_identical_sets(self):
        self.open_page("<p>x</p>")
        calls = self.page.evaluate("""() => [PortalProgress.stallCheck("p", ["a", "b"]), PortalProgress.stallCheck("p", ["b", "a"]),
          PortalProgress.stallCheck("p", ["a"]), PortalProgress.stallCheck("p", []), PortalProgress.stallCheck("p", [])]""")
        self.assertEqual([item["stalled"] for item in calls], [False, True, False, False, False])
        self.assertEqual(calls[1]["repeats"], 2)

    def test_next_denylist_wins_over_allowlist(self):
        self.open_page('<form><label>Name<input value="Ada"></label><button type="button" id="go">Next</button><button type="button" id="other">Submit application</button></form>' + COUNT_CLICKS)
        self.assertEqual(self.page.evaluate("PortalProgress.nextStep().kind"), "ambiguous")
        self.enable_next()
        self.assertEqual(self.guarded()["status"], "refused")
        self.assertEqual(self.page.evaluate("nextClicks"), 0)

    def test_next_allowlist_is_exact_and_unique(self):
        self.open_page('<button type="button" id="a">Save &amp; Continue</button>')
        self.assertEqual(self.page.evaluate("PortalProgress.nextStep().kind"), "next")
        self.open_page('<button type="button">Next</button><button type="button">Continue</button>')
        self.assertEqual(self.page.evaluate("PortalProgress.nextStep().kind"), "ambiguous")
        self.open_page('<button type="button">Next steps for you</button>')
        self.assertEqual(self.page.evaluate("PortalProgress.nextStep().kind"), "none")

    def test_final_review_disables_next(self):
        self.open_page('<h1>Review your application</h1><p>Summary only.</p><button type="button" id="go">Next</button>' + COUNT_CLICKS)
        self.assertTrue(self.page.evaluate("PortalProgress.detectFinalReview().final"))
        self.enable_next()
        self.assertEqual(self.guarded()["reason"], "final_review")
        self.assertEqual(self.page.evaluate("nextClicks"), 0)
        self.open_page('<h1>Your details</h1><label>Name<input value="Ada"></label><button type="button">Finish</button>')
        self.assertTrue(self.page.evaluate("PortalProgress.detectFinalReview().final"))

    def test_generic_adapter_exposes_next_and_final_review(self):
        self.open_page('<label>Name<input value="Ada"></label><button type="button" id="go">Next</button>')
        data = self.page.evaluate("({next: PortalAdapters.forLocation(location.href).nextStep(), final: PortalAdapters.forLocation(location.href).detectFinalReview(document)})")
        self.assertEqual(data["next"]["kind"], "next")
        self.assertFalse(data["final"]["final"])

    def test_guarded_next_off_by_default(self):
        self.open_page('<label>Name<input value="Ada"></label><button type="button" id="go">Next</button>' + COUNT_CLICKS)
        self.assertFalse(self.page.evaluate("PortalProgress.settings.allowGuardedNext"))
        result = self.guarded()
        self.assertEqual((result["status"], result["reason"]), ("refused", "guarded_next_off"))
        self.assertEqual(self.page.evaluate("nextClicks"), 0)

    def test_guarded_next_refuses_missing_stalled_and_clicks_once_when_clear(self):
        self.open_page('<label>Name<input id="n" required></label><button type="button" id="go">Next</button>' + COUNT_CLICKS)
        self.enable_next()
        self.assertEqual(self.guarded()["reason"], "missing_required")
        self.assertEqual(self.guarded()["reason"], "stalled")
        self.page.locator("#n").fill("Ada")
        result = self.guarded()
        self.assertEqual(result["status"], "clicked")
        self.assertEqual(self.page.evaluate("nextClicks"), 1)

    def test_max_15_next_actions(self):
        self.open_page('<label>Name<input value="Ada"></label><button type="button" id="go">Next</button>' + COUNT_CLICKS)
        self.enable_next()
        statuses = [self.guarded() for _ in range(17)]
        self.assertEqual([item["status"] for item in statuses[:15]], ["clicked"] * 15)
        self.assertEqual({item["reason"] for item in statuses[15:]}, {"max_next_actions"})
        self.assertEqual(self.page.evaluate("nextClicks"), 15)

    def test_repeated_rows_unique_refs_survive_reorder(self):
        self.open_page('''<div id="rows">
          <fieldset data-portal-section="employment" id="r1"><legend>Job A</legend><label>Employer<input id="e1"></label></fieldset>
          <fieldset data-portal-section="employment" id="r2"><legend>Job B</legend><label>Employer<input id="e2"></label></fieldset></div>''')
        def ids():
            return {item["structure"]["dom_id"]: item["id"] for item in self.scan() if item["label"] == "Employer"}
        before = ids()
        self.assertEqual(len(set(before.values())), 2)
        self.page.evaluate("rows.insertBefore(r2, r1)")
        self.assertEqual(ids(), before)

    def test_second_upload_skipped(self):
        self.open_page('<label>Resume<input id="up" type="file"></label>')
        field = next(item for item in self.scan() if item["type"] == "file")
        first = self.fill([{"id": field["id"], "value": ""}], {"attachment": ATTACHMENT})[0]
        self.assertEqual(first["status"], "filled")
        field = next(item for item in self.scan() if item["type"] == "file")
        second = self.fill([{"id": field["id"], "value": "", "overwrite": True}], {"attachment": ATTACHMENT})[0]
        self.assertEqual(second["status"], "skipped_existing")

    def test_progress_module_clicks_nothing_without_a_request(self):
        self.open_page('<button type="button" id="go">Next</button>' + COUNT_CLICKS)
        self.page.evaluate("async () => { await PortalProgress.pageCheck(); PortalProgress.nextStep(); PortalProgress.detectFinalReview(); }")
        self.assertEqual(self.page.evaluate("nextClicks"), 0)
        self.assertEqual(self.page.evaluate("syntheticSubmitClicks"), 0)
