from datetime import datetime, timedelta, timezone

import code_gate as g

NOW = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
WD_HOST = "dyson.wd3.myworkdayjobs.com"

# Bodies copy the shape of real verification emails seen 2026-10-28; every secret here is invented.
BODIES = {
    "workday_link": ("Verify your candidate account", "Click this link to confirm your email address and complete setup for your candidate account\n"
                     "https://dyson.wd3.myworkdayjobs.com/dyson_careers/activate/abc123def456/?redirect=%2Fen-US%2Fdyson_careers%2Fjob%2FX%2Fapply%2FuseMyLastApplication\n"
                     "The link will expire after 24 hours."),
    "icims_link": ("Verify your email address", "please verify your email address by clicking the following link:\n\nConfirm my account\n\n"
                   "( https://clicks.icims.com/f/a/AAAA~~/BBBB~/CCCC )\n\nIf this was not you, you can safely delete this email."),
    "eightfold_code": ("Verify your email", "Email Verification\n\n| # Verify your email We just need to verify your email address. Enter the following code below to complete the verification process: 604153 The code will expire after 15 minutes. |"),
    "greenhouse_code": ("Security code for your application to Acme", "Hi Pat,\n\nCopy and paste this code into the security code field on your application:\n# 7xkQ9mTz\n\nAfter you enter the code, resubmit your application."),
    "smartrecruiters_code": ("Your one-time-passcode", "Your one-time-passcode\n358172\nBest regards,\nHiring Team at Acme"),
    "oracle_code": ("Your verification code", "Your verification code is 482916"),
}


def email(kind, sender, minutes_ago=2):
    subject, body = BODIES[kind]
    return {"sender": sender, "subject": subject, "body": body, "sent_at": (NOW - timedelta(minutes=minutes_ago)).isoformat()}


def test_portal_for_host():
    assert g.portal_for_host("acme.wd5.myworkdayjobs.com") == "workday"
    assert g.portal_for_host("jpmc.fa.oraclecloud.com") == "oracle"
    assert g.portal_for_host("job-boards.greenhouse.io") == "greenhouse"
    assert g.portal_for_host("example.com") is None


def test_every_adapter_has_a_sender_entry():
    assert set(g.HOST_PORTAL_HINTS.values()) <= set(g.ALLOWED_SENDER_DOMAINS)


def test_real_shapes_for_each_adapter():
    assert g.vet_email("workday", email("workday_link", "dyson@otp.workday.com"), WD_HOST, NOW)[0] == g.KIND_LINK
    assert g.vet_email("icims", email("icims_link", "no-reply@icims.com"), "career-schwab.icims.com", NOW) == (
        g.KIND_LINK, "https://clicks.icims.com/f/a/AAAA~~/BBBB~/CCCC", None)
    assert g.vet_email("eightfold", email("eightfold_code", "confirm@eightfold.ai"), "x.eightfold.ai", NOW) == (g.KIND_CODE, "604153", None)
    assert g.vet_email("greenhouse", email("greenhouse_code", "no-reply@us.greenhouse-mail.io"), "job-boards.greenhouse.io", NOW) == (g.KIND_CODE, "7xkQ9mTz", None)
    assert g.vet_email("greenhouse", email("greenhouse_code", "no-reply@us.greenhouse-jobs.com"), "job-boards.greenhouse.io", NOW)[0] == g.KIND_CODE
    assert g.vet_email("smartrecruiters", email("smartrecruiters_code", "notifications@smartrecruiters.com"), "jobs.smartrecruiters.com", NOW) == (g.KIND_CODE, "358172", None)
    assert g.vet_email("oracle", email("oracle_code", "gsrecruiting@oracle.com"), "jpmc.fa.oraclecloud.com", NOW) == (g.KIND_CODE, "482916", None)


def test_workday_link_must_be_on_the_session_host_with_activate_path():
    mail = email("workday_link", "dyson@otp.workday.com")
    assert g.vet_email("workday", mail, "other.wd1.myworkdayjobs.com", NOW) == (None, None, g.NOTHING_IN_EMAIL)
    off_path = {**mail, "body": "Click https://dyson.wd3.myworkdayjobs.com/dyson_careers/login/xyz"}
    assert g.vet_email("workday", off_path, WD_HOST, NOW) == (None, None, g.NOTHING_IN_EMAIL)


def test_link_from_a_look_alike_host_is_refused():
    evil = {**email("workday_link", "dyson@otp.workday.com"), "body": "https://dyson.wd3.myworkdayjobs.com.evil.io/activate/abc"}
    assert g.vet_email("workday", evil, WD_HOST, NOW) == (None, None, g.NOTHING_IN_EMAIL)
    evil_icims = {**email("icims_link", "no-reply@icims.com"), "body": "( https://icims.com.evil.io/x )"}
    assert g.vet_email("icims", evil_icims, "career-schwab.icims.com", NOW) == (None, None, g.NOTHING_IN_EMAIL)


def test_wrong_sender_refused_everywhere():
    assert g.vet_email("workday", email("oracle_code", "phish@workday.com.evil.io"), WD_HOST, NOW)[2] == g.SENDER_REFUSED
    assert g.vet_email("oracle", email("oracle_code", "x@oracle.com.evil.io"), "h.oraclecloud.com", NOW)[2] == g.SENDER_REFUSED
    assert g.vet_email("oracle", email("oracle_code", "x@otp.workday.com"), "h.oraclecloud.com", NOW)[2] == g.SENDER_REFUSED


def test_adapters_without_samples_stay_refused():
    for portal in ("lever", "ashby", "taleo"):
        assert g.vet_email(portal, email("oracle_code", "no-reply@lever.co"), "h.example.com", NOW)[2] == g.SENDER_REFUSED


def test_stale_and_future_refused():
    assert g.vet_email("oracle", email("oracle_code", "gsrecruiting@oracle.com", minutes_ago=30), "h", NOW)[2] == g.CODE_STALE
    assert g.vet_email("oracle", email("oracle_code", "gsrecruiting@oracle.com", minutes_ago=-5), "h", NOW)[2] == g.CODE_STALE


def test_email_with_nothing_usable():
    mail = {**email("oracle_code", "gsrecruiting@oracle.com"), "body": "Welcome to the portal."}
    assert g.vet_email("oracle", mail, "h", NOW)[2] == g.NOTHING_IN_EMAIL


def test_bad_email_shapes():
    assert g.vet_email("workday", {"sender": "a@otp.workday.com"}, WD_HOST, NOW)[2] == g.BAD_EMAIL_FILE
    assert g.vet_email("workday", {**email("oracle_code", "a@otp.workday.com"), "sent_at": "not a date"}, WD_HOST, NOW)[2] == g.BAD_EMAIL_FILE


def test_enter_refuses_unknown_portal_without_touching_browser():
    class Boom:
        def __getattr__(self, name):
            raise AssertionError("browser touched")

    assert g.enter(Boom(), "https://example.com/login", email("oracle_code", "gsrecruiting@oracle.com")) == {"result": g.PORTAL_UNKNOWN}
