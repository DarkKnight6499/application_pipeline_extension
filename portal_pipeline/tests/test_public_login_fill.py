"""login_fill on synthetic pages with a fake secret created at runtime; the secret must never leave the page."""
import json
import secrets
import sys
from pathlib import Path

# Config
SOURCE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = SOURCE_DIR / "tests"
SESSION_URL = "https://login-fixture.myworkdayjobs.com/en-US/careers/job/apply"
OTHER_URL = "https://login-fixture.myworkdayjobs.com.attacker.invalid/signin"
USER = "fixture.user@example.invalid"
FORM = ('<form><label>Email Address<input id="user" type="text"></label><label>Password<input id="pw" type="password"></label>'
        '<button type="button" id="signin">Sign In</button></form>')
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(TEST_DIR))
import login_fill
from browser_test_support import SyntheticBrowserTest


class LoginFillTests(SyntheticBrowserTest):
    def setUp(self):
        super().setUp()
        self.secret = secrets.token_hex(12)
        self.calls = []

    def get_login(self, host):
        self.calls.append(host)
        return (USER, self.secret)

    def values(self):
        return self.page.evaluate("[document.getElementById('user')?.value, document.getElementById('pw')?.value]")

    def assert_clean(self, result, capsys, caplog):
        captured = capsys.readouterr()
        blob = json.dumps(result) + captured.out + captured.err + caplog.text
        self.assertNotIn(self.secret, blob)

    def test_fills_username_and_password_on_exact_host(self):
        self.open_markup(FORM, url=SESSION_URL)
        result = login_fill.login(self.page, SESSION_URL, get_login=self.get_login)
        self.assertEqual(result, {"result": "filled"})
        self.assertEqual(self.values(), [USER, self.secret])
        self.assertEqual(self.calls, ["login-fixture.myworkdayjobs.com"])
        self.assertEqual(self.page.evaluate("syntheticSubmitClicks"), 0)

    def test_mismatched_host_is_refused_without_reading_the_login(self):
        self.open_markup(FORM, url=OTHER_URL)
        result = login_fill.login(self.page, SESSION_URL, get_login=self.get_login)
        self.assertEqual(result["result"], "host_mismatch")
        self.assertEqual((self.calls, self.values()), ([], ["", ""]))

    def test_captcha_stops_before_typing(self):
        self.open_markup(FORM + '<iframe src="https://www.google.com/recaptcha/api2/anchor" width="300" height="80"></iframe>', url=SESSION_URL)
        self.assertEqual(login_fill.login(self.page, SESSION_URL, get_login=self.get_login)["result"], "captcha")
        self.assertEqual(self.values(), ["", ""])

    def test_authenticator_prompt_stops_before_typing(self):
        self.open_markup(FORM + "<p>Open your authenticator app and approve this sign in.</p>", url=SESSION_URL)
        self.assertEqual(login_fill.login(self.page, SESSION_URL, get_login=self.get_login)["result"], "authenticator")
        self.assertEqual(self.values(), ["", ""])

    def test_create_account_form_with_two_passwords_is_not_filled(self):
        self.open_markup(FORM.replace("</form>", '<label>Verify Password<input id="pw2" type="password"></label></form>'), url=SESSION_URL)
        self.assertEqual(login_fill.login(self.page, SESSION_URL, get_login=self.get_login)["result"], "no_login_form")
        self.assertEqual(self.values(), ["", ""])

    def test_missing_credentials_type_nothing(self):
        self.open_markup(FORM, url=SESSION_URL)
        self.assertEqual(login_fill.login(self.page, SESSION_URL, get_login=lambda host: None)["result"], "no_credentials")
        self.assertEqual(self.values(), ["", ""])

    def test_secret_never_appears_in_output_logs_or_report(self):
        import contextlib
        import io
        import logging
        stream, handler = io.StringIO(), logging.StreamHandler()
        logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        self.open_markup(FORM, url=SESSION_URL)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = login_fill.login(self.page, SESSION_URL, get_login=self.get_login)
            print(result)
        self.assertEqual(self.values()[1], self.secret)
        self.assertNotIn(self.secret, out.getvalue() + err.getvalue() + json.dumps(result) + stream.getvalue())

    def test_failure_report_carries_no_secret(self):
        self.open_markup(FORM, url=SESSION_URL)
        self.page.evaluate("document.getElementById('pw').disabled = true")
        self.page.set_default_timeout(500)
        result = login_fill.login(self.page, SESSION_URL, get_login=self.get_login)
        self.assertEqual(result["result"], "error")
        self.assertNotIn(self.secret, json.dumps(result))

    def test_code_goes_only_into_a_field_labeled_as_a_code(self):
        self.open_markup('<label>Search jobs<input id="search"></label><label>Verification Code<input id="code"></label>', url=SESSION_URL)
        self.assertEqual(login_fill.enter_code(self.page, SESSION_URL, "483920")["result"], "code_typed")
        self.assertEqual(self.page.evaluate("[document.getElementById('search').value, document.getElementById('code').value]"), ["", "483920"])

    def test_code_with_no_code_field_types_nothing(self):
        self.open_markup('<label>Search jobs<input id="search"></label><label>Email<input id="mail"></label>', url=SESSION_URL)
        self.assertEqual(login_fill.enter_code(self.page, SESSION_URL, "483920")["result"], "code_field_missing")
        self.assertEqual(self.page.evaluate("[document.getElementById('search').value, document.getElementById('mail').value]"), ["", ""])

    def test_code_refused_on_other_host_and_for_bad_values(self):
        self.open_markup('<label>Verification Code<input id="code"></label>', url=OTHER_URL)
        self.assertEqual(login_fill.enter_code(self.page, SESSION_URL, "483920")["result"], "host_mismatch")
        self.open_markup('<label>Verification Code<input id="code"></label>', url=SESSION_URL)
        self.assertEqual(login_fill.enter_code(self.page, SESSION_URL, "12 34; DROP")["result"], "code_rejected")
        self.assertEqual(self.page.evaluate("document.getElementById('code').value"), "")

    def test_code_extracted_from_supplied_email_text_only(self):
        self.assertEqual(login_fill.code_from_email("Your verification code", "Your verification code is 483920."), "483920")
        self.assertIsNone(login_fill.code_from_email("Newsletter", "Nothing to see"))
