"""Run driver safety helpers: tab choice, Next button text, required gaps, what may be learned."""
import sys
import unittest

from browser_test_support import HERE

sys.path.insert(0, str(HERE))
import workday_run


def field(**kw):
    base = {"required": True, "blocked": False, "current": "", "proposal": "", "type": "text", "record": None, "label": "Q", "disabled": False}
    return {**base, **kw}


class DriverSafetyTests(unittest.TestCase):
    def test_only_real_workday_hosts_are_workday_tabs(self):
        self.assertTrue(workday_run.is_workday_url("https://citi.wd5.myworkdayjobs.com/en-US/2/apply"))
        self.assertFalse(workday_run.is_workday_url("https://unrelated.example/?return=myworkdayjobs.com"))
        self.assertFalse(workday_run.is_workday_url("https://evilmyworkdayjobs.com/x"))

    def test_next_button_text_must_match_exactly(self):
        self.assertTrue(workday_run.is_next_label(" Save and Continue "))
        self.assertFalse(workday_run.is_next_label("Submit application and go to next"))
        self.assertFalse(workday_run.is_next_label("Submit"))

    def test_required_empty_field_with_a_proposal_still_counts_as_a_gap(self):
        self.assertEqual(len(workday_run.unanswered([field(proposal="2023")])), 1)
        self.assertEqual(workday_run.unanswered([field(current="2023")]), [])

    def test_learning_skips_history_row_fields(self):
        row = field(current="Intern", record={"id": "x"})
        loose = field(current="Yes", label="Are you over 18?")
        self.assertEqual([f["label"] for f in workday_run.learnable([row, loose])], ["Are you over 18?"])


class PortalHostTests(unittest.TestCase):
    def test_oracle_mode_accepts_only_oraclecloud_hosts(self):
        workday_run.PORTAL["oracle"] = True
        try:
            self.assertTrue(workday_run.is_workday_url("https://jpmc.fa.oraclecloud.com/hcmUI/x"))
            self.assertFalse(workday_run.is_workday_url("https://citi.wd5.myworkdayjobs.com/x"))
            self.assertFalse(workday_run.is_workday_url("https://evil.example/?u=oraclecloud.com"))
        finally:
            workday_run.PORTAL["oracle"] = False


class LearnableDuplicateTests(unittest.TestCase):
    def test_a_label_that_appears_twice_is_never_learned(self):
        code = field(current="+1", label="Phone Number", type="combobox")
        number = field(current="(862) 452-0144", label="Phone Number")
        other = field(current="Yes", label="Are you over 18?")
        self.assertEqual([f["label"] for f in workday_run.learnable([code, number, other])], ["Are you over 18?"])


def test_learnable_skips_option_ids_and_account_fields():
    base = {"blocked": False, "proposal": "", "record": None, "required": False}
    fields = [dict(base, label="Type", type="select-one", current="15145"),
              dict(base, label="Login", type="text", current="a@b.c"),
              dict(base, label="Zip/Postal Code", type="text", current="07029")]
    assert [f["label"] for f in workday_run.learnable(fields)] == ["Zip/Postal Code"]


def test_sponsorship_selection_overwrites_prefilled_value():
    assert workday_run.selection_for({"id": "a", "proposal": "No", "key": "sponsorship_now"}) == {"id": "a", "value": "No", "overwrite": True}
    assert workday_run.selection_for({"id": "b", "proposal": "Yes", "key": "authorized_us"}) == {"id": "b", "value": "Yes"}


def test_learnable_skips_immigration_questions():
    base = {"blocked": False, "proposal": "", "record": None, "type": "select-one", "current": "Yes"}
    fields = [dict(base, label="If you currently hold OPT, are you eligible for a 24-month extension?"),
              dict(base, label="Do you require visa sponsorship?"),
              dict(base, label="Are you at least 18?")]
    assert [f["label"] for f in workday_run.learnable(fields)] == ["Are you at least 18?"]
