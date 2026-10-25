"""Browser safety probes using invented pages, values and attachment bytes only."""
import base64
import hashlib
import sys
import unittest
from pathlib import Path

# Config
SOURCE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = SOURCE_DIR / "tests"
RESUME_BYTES = b"Invented reviewed bytes"
ATTACHMENT_NAME = "Synthetic.pdf"
ATTACHMENT = {"name": ATTACHMENT_NAME, "mime": "application/pdf",
              "base64": base64.b64encode(RESUME_BYTES).decode("ascii"),
              "sha256": hashlib.sha256(RESUME_BYTES).hexdigest()}
UPLOAD_PAGE = '''<div data-automation-id="attachments-FileUpload-container">
<label for="resume">Resume</label><input id="resume" type="file" data-automation-id="file-upload-input-ref">
<span id="confirmation"></span></div><script>
window.changes = 0;
document.getElementById('resume').addEventListener('change', event => {
window.changes++; document.getElementById('confirmation').textContent = event.target.files[0].name;
});</script>'''
MENU_PAGE = '''<fieldset><legend>Invented category</legend>
<button id="menu" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="options">Select One</button>
<div id="options" role="listbox" hidden><div id="option" role="option">Alpha</div></div></fieldset>
<script>window.optionClicks=0;
const menu=document.getElementById('menu'), popup=document.getElementById('options'), option=document.getElementById('option');
menu.addEventListener('click',()=>{menu.setAttribute('aria-expanded','true'); popup.hidden=false;});
option.addEventListener('click',()=>{window.optionClicks++; menu.textContent=option.textContent;});
</script>'''
sys.path.insert(0, str(TEST_DIR))
from browser_test_support import SyntheticBrowserTest


class BrowserSafetyTests(SyntheticBrowserTest):
    def upload_page(self):
        self.open_markup(UPLOAD_PAGE)
        self.page.add_script_tag(path=str(SOURCE_DIR / "extension" / "workday-upload.js"))

    def test_upload_guard_rechecked_after_checksum_before_assignment(self):
        self.upload_page()
        result = self.page.evaluate('''async attachment => {
          const original=crypto.subtle.digest.bind(crypto.subtle);
          window.stopUpload=false;
          crypto.subtle.digest=async (...args)=>{const digest=await original(...args); window.stopUpload=true; return digest;};
          let error='';
          try { await PortalWorkdayUpload.upload(document.getElementById('resume'), attachment,
            ()=>{if(window.stopUpload) throw new Error('Synthetic guard stopped');}); }
          catch(e){error=e.message;}
          return {error, files:document.getElementById('resume').files.length, changes:window.changes};
        }''', ATTACHMENT)
        self.assertEqual(result["files"], 0, result)
        self.assertEqual(result["changes"], 0, result)

    def test_same_name_different_bytes_not_accepted_as_reviewed_resume(self):
        self.upload_page()
        result = self.page.evaluate('''async attachment => {
          const input=document.getElementById('resume'), transfer=new DataTransfer();
          transfer.items.add(new File(['Wrong synthetic bytes'], attachment.name)); input.files=transfer.files;
          document.getElementById('confirmation').textContent=attachment.name;
          try { return {accepted:true, result:await PortalWorkdayUpload.upload(input, attachment)}; }
          catch(e){return {accepted:false, error:e.message};}
        }''', ATTACHMENT)
        self.assertFalse(result["accepted"], result)

    def test_disabled_upload_is_not_assigned(self):
        self.upload_page()
        result = self.page.evaluate('''async attachment => {
          const input=document.getElementById('resume'); input.disabled=true;
          try {await PortalWorkdayUpload.upload(input,attachment);} catch(e){}
          return {files:input.files.length, changes:window.changes};
        }''', ATTACHMENT)
        self.assertEqual(result["files"], 0, result)

    def test_history_answer_memory_does_not_override_distinct_profile_records(self):
        self.open_markup('''<div data-portal-section="employment"><label>Company<input id="one"></label></div>
          <div data-portal-section="employment"><label>Company<input id="two"></label></div>''')
        fields = self.page.evaluate('''() => {
          const profile={values:{'employment.0.company':{value:'Invented Alpha',source:'synthetic'},
            'employment.1.company':{value:'Invented Beta',source:'synthetic'}}, answers:{company:'Invented remembered company'}};
          const first=PortalEngine.scan(profile), bindings={};
          first.filter(f=>f.record).forEach((f,i)=>{bindings[f.record.id]=i;});
          return PortalEngine.scan(profile,{bindings}).filter(f=>f.record).map(f=>({key:f.key,proposal:f.proposal}));
        }''')
        self.assertEqual([field["proposal"] for field in fields], ["Invented Alpha", "Invented Beta"], fields)

    def menu_page(self):
        self.open_markup(MENU_PAGE)
        self.page.add_script_tag(path=str(SOURCE_DIR / "extension" / "workday-menu.js"))

    def test_menu_rechecks_disabled_option_before_click(self):
        self.menu_page()
        result = self.page.evaluate('''async () => {
          const option=document.getElementById('option');
          option.scrollIntoView=()=>option.setAttribute('aria-disabled','true');
          let error=''; try {await PortalWorkdayMenu.choose(document.getElementById('menu'),'Alpha');}
          catch(e){error=e.message;}
          return {clicks:window.optionClicks,error};
        }''')
        self.assertEqual(result["clicks"], 0, result)

    def test_menu_rechecks_option_label_before_click(self):
        self.menu_page()
        result = self.page.evaluate('''async () => {
          const option=document.getElementById('option');
          option.scrollIntoView=()=>{option.textContent='Beta';};
          let error=''; try {await PortalWorkdayMenu.choose(document.getElementById('menu'),'Alpha');}
          catch(e){error=e.message;}
          return {clicks:window.optionClicks,error,value:document.getElementById('menu').textContent};
        }''')
        self.assertEqual(result["clicks"], 0, result)

    def test_driver_fill_stops_when_dialog_appears_between_fields(self):
        self.open_markup('''<div data-automation-id="progressBarActiveStep">My Information</div>
          <label>First Name<input id="first"></label><label>Last Name<input id="last"></label>
          <script>document.getElementById('first').addEventListener('change',()=>{
            const modal=document.createElement('div'); modal.setAttribute('role','dialog');
            modal.textContent='Invented confirmation'; document.body.append(modal);
          });</script>''')
        sys.path.insert(0, str(SOURCE_DIR))
        import workday_run
        fields = self.scan({"first_name": {"value": "Invented", "source": "synthetic"},
                            "last_name": {"value": "Candidate", "source": "synthetic"}})
        picks = [{"id": field["id"], "value": field["proposal"]} for field in fields if field["key"]]
        results = self.page.evaluate(workday_run.FILL_JS, picks)
        self.assertEqual(self.page.locator("#last").input_value(), "", results)
        self.assertTrue(all(result["status"] == "failed" for result in results), results)

    def test_driver_fill_stops_when_review_appears_between_fields(self):
        self.open_markup('''<div data-automation-id="progressBarActiveStep">My Information</div>
          <label>First Name<input id="first"></label><label>Last Name<input id="last"></label>
          <script>document.getElementById('first').addEventListener('change',()=>{
            document.querySelector('[data-automation-id=progressBarActiveStep]').textContent='Review';
          });</script>''')
        sys.path.insert(0, str(SOURCE_DIR))
        import workday_run
        fields = self.scan({"first_name": {"value": "Invented", "source": "synthetic"},
                            "last_name": {"value": "Candidate", "source": "synthetic"}})
        picks = [{"id": field["id"], "value": field["proposal"]} for field in fields if field["key"]]
        results = self.page.evaluate(workday_run.FILL_JS, picks)
        self.assertEqual(self.page.locator("#last").input_value(), "", results)
        self.assertTrue(all(result["status"] == "failed" for result in results), results)


if __name__ == "__main__":
    unittest.main(verbosity=2)
