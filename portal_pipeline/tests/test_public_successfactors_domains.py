"""Author: Yazad Madan. Fabricated RMK routing and read-only detection regressions."""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Config
HERE = Path(__file__).resolve().parents[1]
CUSTOM_ORIGIN = "https://careers.example.invalid"
APPLY_URL = CUSTOM_ORIGIN + "/talentcommunity/apply/1234567890/?locale=en_US"
JOB_URL = CUSTOM_ORIGIN + "/job/Fabricated-Role/1234567890/"
PROVIDENT_ORIGIN = "https://careers.provident.bank"
NODE = shutil.which("node")
sys.path.insert(0, str(HERE))

import apply as application
import workday_run


class SuccessFactorsDomainTests(unittest.TestCase):
    def test_custom_apply_path_routes_without_browser(self):
        self.assertEqual(application.portal_for(APPLY_URL), "successfactors")

    def test_provident_exact_host_mapping(self):
        for path in ("/", "/talentcommunity/apply/1234567890/", "/job/Fabricated-Role/1234567890/"):
            self.assertEqual(application.portal_for(PROVIDENT_ORIGIN + path), "successfactors")

    def test_vendor_domain_mapping(self):
        for host in ("career5.successfactors.com", "jobs.successfactors.eu", "jobs.sapsf.com", "jobs.jobs2web.com"):
            self.assertEqual(application.portal_for("https://" + host + "/x"), "successfactors")

    def test_unrelated_and_spoof_hosts_do_not_route(self):
        for url in (CUSTOM_ORIGIN + "/job/Fabricated-Role/1234567890/", CUSTOM_ORIGIN + "/apply/123",
                    "https://careers.provident.bank.example.invalid/", "https://notsuccessfactors.com/",
                    APPLY_URL.replace("1234567890", "abc"), APPLY_URL.replace("/?", "/extra?"),
                    APPLY_URL.replace("https:", "http:")):
            self.assertIsNone(application.portal_for(url), url)

    def test_resolve_custom_apply_and_driver_option(self):
        job = application.resolve(APPLY_URL, None)
        self.assertEqual(workday_run.parse_args(application.driver_args(job)).portal, "successfactors")

    def test_job_page_uses_only_bound_tab_signals(self):
        page = SimpleNamespace(url=JOB_URL)
        with patch.object(application, "sync_playwright") as start, \
                patch.object(application, "select_tab", return_value=page) as select, \
                patch("successfactors.matches_page", return_value=True):
            browser = start.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value
            job = application.resolve(JOB_URL, None, target_id="fabricated-target")
        self.assertEqual(job["portal"], "successfactors")
        select.assert_called_once_with(browser, JOB_URL, "fabricated-target")
        browser.close.assert_called_once()

    def test_unrelated_bound_tab_cannot_classify_job(self):
        page = SimpleNamespace(url="https://other.example.invalid/talentcommunity/apply/123/")
        with patch.object(application, "sync_playwright"), patch.object(application, "select_tab", return_value=page), \
                patch("successfactors.matches_page", return_value=True) as matches:
            with self.assertRaisesRegex(SystemExit, "No adapter"):
                application.resolve(JOB_URL, None, target_id="fabricated-target")
        matches.assert_not_called()

    def test_driver_accepts_only_bound_custom_host(self):
        settings = workday_run.settings_for("successfactors")
        settings["host"] = "careers.example.invalid"
        token = workday_run.PORTAL_CONTEXT.set(settings)
        try:
            self.assertTrue(settings["single"])
            self.assertFalse(workday_run.plain_workday())
            self.assertTrue(workday_run.is_workday_url(APPLY_URL))
            self.assertFalse(workday_run.is_workday_url("https://other.example.invalid/talentcommunity/apply/123/"))
            self.assertFalse(workday_run.is_workday_url(APPLY_URL.replace("https:", "http:")))
            self.assertEqual(workday_run.bind_rows(MagicMock(), {}), {})
            self.assertTrue(workday_run.ensure_rows(MagicMock(), {}))
        finally:
            workday_run.PORTAL_CONTEXT.reset(token)

    def test_execute_dry_injects_sf_and_stops_before_writes_or_navigation(self):
        page = MagicMock()
        del page.page
        page.url = APPLY_URL
        args = workday_run.parse_args(["--portal", "successfactors", "--dry", "--job-url", APPLY_URL,
                                      "--target-id", "fabricated-target"])
        with patch.object(workday_run, "sync_playwright") as start, \
                patch.object(workday_run, "select_tab", return_value=page), \
                patch("successfactors.matches_page", return_value=True), \
                patch.object(workday_run, "dialog_open", return_value=False), \
                patch.object(workday_run, "build_profile", return_value={}), \
                patch.object(workday_run, "run_page", return_value=[]) as scan, \
                patch.object(workday_run.single_upload, "upload") as upload, \
                contextlib.redirect_stdout(io.StringIO()):
            report = workday_run.execute(args)
        self.assertEqual(report.data["exit_code"], 0)
        self.assertEqual(report.data["stop_reason"], "Dry run finished; nothing was written.")
        self.assertTrue(scan.call_args.args[2])
        sources = [call.args[1]["expression"] for call in page.context.new_cdp_session.return_value.send.call_args_list]
        self.assertTrue(any("PortalSuccessFactorsDetection = {matches}" in source for source in sources))
        self.assertTrue(any('id: "successfactors-cli"' in source for source in sources))
        upload.assert_not_called()
        page.locator.assert_not_called()
        start.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value.close.assert_called_once()


@unittest.skipUnless(NODE, "Node is required for actual JavaScript detection checks.")
class SuccessFactorsJavaScriptTests(unittest.TestCase):
    def evaluate(self, body):
        source = "const fs = require('fs'), vm = require('vm');\n" + body
        result = subprocess.run([NODE, "-e", source], cwd=HERE, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_detector_positive_and_negative_signals_without_form_reads(self):
        result = self.evaluate(r"""
const context = vm.createContext({URL});
vm.runInContext(fs.readFileSync('extension/successfactors-detection.js', 'utf8'), context);
const cases = [
  ['/talentcommunity/apply/1234567890/', [], [], true],
  ['/job/Fabricated-Role/1234567890/', ['https://rmkcdn.successfactors.com/assets/site.js'], [], true],
  ['/job/Fabricated-Role/1234567890/', [], ['SAP SuccessFactors Recruiting Marketing'], true],
  ['/profile/', ['https://rmkcdn.successfactors.com/assets/site.js'], ['SAP SuccessFactors Recruiting Marketing'], true],
  ['/job/Fabricated-Role/1234567890/', [], [], false],
  ['/job/Fabricated-Role/1234567890/', ['https://rmkcdn.successfactors.com.evil.example.invalid/a.js'], [], false],
  ['/about/', ['https://rmkcdn.successfactors.com/a.js'], [], false],
  ['/job/Fabricated-Role/not-numeric/', ['https://rmkcdn.successfactors.com/a.js'], [], false]
];
const results = cases.map(([path, assets, generators, expected]) => {
  const doc = {baseURI: 'https://careers.example.invalid/', querySelectorAll(selector) {
    if (selector === 'script[src],link[href]') return assets.map(url => ({getAttribute: name => name === 'src' ? url : null}));
    if (selector === 'meta[name="generator"]') return generators.map(value => ({getAttribute: () => value}));
    throw Error('Unexpected DOM read: ' + selector);
  }};
  return context.PortalSuccessFactorsDetection.matches('https://careers.example.invalid' + path, doc) === expected;
});
console.log(JSON.stringify(results));
""")
        self.assertEqual(result, [True] * 8)

    def test_cli_adapter_keeps_protected_answers_manual_and_refuses_direct_fill(self):
        result = self.evaluate(r"""
const fields = ['First name', 'Current sponsorship', 'Future sponsorship', 'Work authorization', 'Consent to privacy terms',
  'I attest this is true', 'Gender', 'Veteran status', 'Visa type'].map(label => ({label, type: 'text',
  status: 'prepared', proposal: 'Synthetic', current: '', structure: {}, record: null}));
const context = vm.createContext({URL, location: {href: 'https://careers.example.invalid/talentcommunity/apply/123/'},
  document: {}, PortalEngine: {core: {scan: () => fields, fill: () => {throw Error('Protected fill reached writer');}}}});
for (const file of ['adapters/registry.js', 'adapters/generic.js', 'adapters/successfactors.js',
  'successfactors-detection.js', 'successfactors-live.js']) {
  vm.runInContext(fs.readFileSync('extension/' + file, 'utf8'), context);
}
const adapter = context.PortalAdapters.forLocation(context.location.href), scanned = adapter.scan({});
console.log(JSON.stringify([scanned[0].status, ...scanned.slice(1).map(field => field.status),
  adapter.fill({field: scanned[1]}, {id: 'manual'}, {}).status, adapter.id,
  context.PortalAdapters.forLocation('https://careersXexampleXinvalid/').id,
  context.PortalSuccessFactorsAdapter.hosts.length]));
""")
        self.assertEqual(result, ["prepared", *(["manual_only"] * 8), "refused", "successfactors-cli", "generic", 0])

    def test_handoff_provident_mapping_is_prepared(self):
        result = self.evaluate(r"""
const context = vm.createContext({URL, location: {href: 'https://careers.example.invalid/'}});
vm.runInContext(fs.readFileSync('extension/handoff.js', 'utf8'), context);
console.log(JSON.stringify(context.PortalHandoff.resolve('https://careers.provident.bank/')));
""")
        self.assertEqual((result["ats"], result["support"]), ("successfactors", "prepared"))


if __name__ == "__main__":
    unittest.main()
