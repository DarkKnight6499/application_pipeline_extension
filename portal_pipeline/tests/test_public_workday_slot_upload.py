"""Author: Yazad Madan. Slot ownership and stale Workday resume replacement."""
import contextlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from browser_test_support import SyntheticBrowserTest
import workday_attachments as attachments
import workday_run as driver

# Config
SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "workday-upload.js"
NAME = "Synthetic_Resume.docx"
PAYLOAD = b"r" * 11749
NODE_HARNESS = r"""
const fs = require('node:fs'), vm = require('node:vm'), {File} = require('node:buffer');
const bytes = Buffer.alloc(11749, 'r'), name = 'Synthetic_Resume.docx';
async function run(kind) {
  let clicks = 0, writes = 0;
  const body = {}, roots = [];
  function slot(id, title, identity, attached) {
    const root = {id, isConnected: true, parentElement: body, children: [],
      get textContent() {return title + ' ' + this.children.map(n => n.textContent || '').join(' ');},
      get innerText() {return this.textContent;},
      getAttribute: key => key === 'data-automation-id' ? identity : null,
      cloneNode: () => ({textContent: title, querySelectorAll: () => []}),
      contains(node) {return this.children.includes(node);},
      querySelectorAll(selector) {
        if (selector.startsWith('input')) return this.children.filter(n => n.input);
        if (selector.startsWith('button')) return this.children.filter(n => n.item).map(n => n.deletion);
        if (selector.includes('file-upload-item')) return this.children.filter(n => n.item);
        return [];
      }};
    const input = {input: true, parentElement: root, isConnected: true, multiple: true, files: [], labels: [],
      matches: selector => selector !== ':disabled', getAttribute: () => null,
      dispatchEvent() {writes++; root.children.push({item: true, textContent: name + (kind === 'wrong_size' ? ' 11.41 KB' : ' 11.47 KB')});}};
    root.children.push(input);
    if (attached) {
      const item = {item: true, textContent: name + ' 11.41 KB'};
      const deletion = {type: 'button', textContent: 'Remove', getAttribute: () => null,
        getClientRects: () => [1], closest: () => null,
        click() {clicks++; root.children = root.children.filter(n => !n.item); input.files = [];}};
      item.deletion = deletion; root.children.push(item);
      if (kind === 'duplicate') root.children.push({...item});
    }
    roots.push(root); return {root, input};
  }
  const resume = slot('resume', 'Upload a file', 'formField-resume', true);
  const cert = slot('certification', 'Attachments', 'formField-certification', false);
  const cover = slot('cover', 'Attachments (optional)', 'formField-attachments', false);
  const document = {body, querySelectorAll: selector => selector.startsWith('input')
    ? roots.flatMap(n => n.querySelectorAll(selector)) : roots};
  const context = vm.createContext({document, Uint8Array, File, atob, Event, performance, setTimeout,
    crypto: require('node:crypto').webcrypto,
    DataTransfer: class {constructor() {this.files = []; this.items = {add: file => this.files.push(file)};}}});
  vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
  const api = context.PortalWorkdayUpload, found = api.find() === resume.input;
  const before = api.inspectSlot('resume');
  const result = await api.replace({name, mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    base64: bytes.toString('base64'), sha256: require('node:crypto').createHash('sha256').update(bytes).digest('hex')},
    'resume', () => {}, {timeout: 0});
  return {found, before, result, clicks, writes, otherFiles: [cert.input.files.length, cover.input.files.length]};
}
(async () => process.stdout.write(JSON.stringify({normal: await run('normal'), duplicate: await run('duplicate'), wrongSize: await run('wrong_size')})))();
"""
PAGE = '''<div data-automation-id="progressBarActiveStep">My Experience</div>
<div data-automation-id="file-upload-page">
<div id="resume-slot" data-automation-id="formField-resume"><h3>Upload a file</h3>
<div data-automation-id="file-upload-zone"><input id="resume" type="file" multiple hidden data-automation-id="file-upload-input-ref"></div>
<div data-automation-id="file-upload-item"><span data-automation-id="fileName">Synthetic_Resume.docx</span> 11.41 KB
<button type="button" data-automation-id="delete-file">Remove</button></div></div>
<fieldset><legend>Certifications</legend><label>Attachments<input id="certification" type="file" multiple data-automation-id="file-upload-input-ref"></label></fieldset>
<div data-automation-id="formField-attachments"><label>Attachments (optional)<input id="cover" type="file" multiple data-automation-id="file-upload-input-ref"></label></div>
</div><script>
window.removals = 0; window.uploads = 0;
document.querySelector('[data-automation-id="delete-file"]').onclick = event => {
  window.removals++; event.target.closest('[data-automation-id="file-upload-item"]').remove();
};
document.getElementById('resume').onchange = event => {
  window.uploads++;
  const file = event.target.files[0], item = document.createElement('div');
  item.setAttribute('data-automation-id', 'file-upload-item');
  item.textContent = file.name + ' ' + (file.size / 1024).toFixed(2) + ' KB';
  document.getElementById('resume-slot').append(item);
};
</script>'''


class WorkdaySlotModelTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_actual_adapter_owns_resume_with_three_workday_inputs(self):
        output = subprocess.run(["node", "-e", NODE_HARNESS, str(SCRIPT)],
                                capture_output=True, text=True, check=True, timeout=10)
        cases = json.loads(output.stdout)
        normal = cases["normal"]
        self.assertTrue(normal["found"])
        self.assertEqual(normal["before"]["status"], "ready")
        self.assertTrue(normal["result"]["confirmed"])
        self.assertEqual(normal["result"]["removal"], "removed")
        self.assertEqual((normal["clicks"], normal["writes"], normal["otherFiles"]), (1, 1, [0, 0]))
        duplicate = cases["duplicate"]
        self.assertEqual(duplicate["result"]["status"], "ambiguous")
        self.assertEqual((duplicate["clicks"], duplicate["writes"]), (0, 0))
        self.assertFalse(cases["wrongSize"]["result"]["confirmed"])
        self.assertTrue(cases["wrongSize"]["result"]["size_mismatch"])


class WorkdaySlotUploadTests(SyntheticBrowserTest):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.resume = Path(folder.name) / NAME
        self.resume.write_bytes(PAYLOAD)
        self.open_markup(PAGE)
        self.page.add_script_tag(path=str(SCRIPT))

    def assert_only_resume_changed(self):
        self.assertEqual(self.page.evaluate("[removals, uploads]"), [1, 1])
        self.assertEqual(self.page.evaluate("[document.getElementById('certification').files.length, document.getElementById('cover').files.length]"), [0, 0])

    def test_find_uses_resume_owner_among_three_inputs(self):
        self.assertTrue(self.page.evaluate("PortalWorkdayUpload.find() === document.getElementById('resume')"))
        self.assertEqual(self.page.evaluate("PortalWorkdayUpload.inspectSlot('resume')"),
                         {"status": "ready", "subtype": "resume", "attached": True})

    def test_replace_deletes_stale_resume_and_confirms_name_and_size(self):
        result = self.page.evaluate("attachment => PortalWorkdayUpload.replace(attachment, 'resume', () => {}, {timeout: 200})",
                                    driver.attachment_for(self.resume))
        self.assertEqual((result["status"], result["removal"], result["observed_filename"]), ("confirmed", "removed", NAME))
        self.assertTrue(result["confirmed"])
        self.assert_only_resume_changed()

    def test_two_items_in_resume_slot_refuse_without_deleting(self):
        self.page.evaluate("() => { const item = document.querySelector('[data-automation-id=file-upload-item]'); item.after(item.cloneNode(true)); }")
        result = self.page.evaluate("attachment => PortalWorkdayUpload.replace(attachment, 'resume', () => {}, {timeout: 0})",
                                    driver.attachment_for(self.resume))
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(self.page.evaluate("[removals, uploads]"), [0, 0])

    def test_python_verifier_replaces_resume_with_other_empty_inputs(self):
        args = SimpleNamespace(resume=self.resume, cover=None)
        report = driver.RunReport()
        event = report.new_page("My Experience")
        attachments.verify(self.page, args, report, event, guard=lambda: None, boundary_js="() => {}")
        self.assertEqual(report.data["attachment_check"]["resume"]["status"], "matched")
        self.assertEqual(event["uploads"][0]["status"], "verified")
        self.assert_only_resume_changed()

    def test_python_verifier_ignores_unowned_empty_certification_input(self):
        self.page.evaluate("document.getElementById('certification').parentElement.firstChild.textContent = 'Certificate file'")
        snapshot = self.page.evaluate(attachments.READ_JS)
        self.assertEqual(snapshot["unknown_inputs"], [1])
        args = SimpleNamespace(resume=self.resume, cover=None)
        report = driver.RunReport()
        event = report.new_page("My Experience")
        attachments.verify(self.page, args, report, event, guard=lambda: None, boundary_js="() => {}")
        self.assertEqual(event["uploads"][0]["status"], "verified")
        self.assert_only_resume_changed()

    def test_driver_records_resume_replacement_before_field_fill(self):
        args = SimpleNamespace(resume=self.resume, cover=None)
        report = driver.RunReport()
        event = report.new_page("My Experience")
        with contextlib.redirect_stdout(None):
            driver.verify_workday_attachments(self.page, args, report, event)
        self.assertEqual(len(event["uploads"]), 1)
        self.assertEqual(event["uploads"][0]["sha256"], driver.sha256_file(self.resume))
        self.assertEqual(event["uploads"][0]["status"], "verified")
        self.assert_only_resume_changed()
