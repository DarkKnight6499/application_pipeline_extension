"""Sponsorship label detection and answers; marketing opt-in/opt-out wording must stay untouched."""
import pytest

import workday_run as w

# Config
NOT_SPONSORSHIP = [
    "Opt in to text messages",
    "Opt-in to receive job alerts by email",
    "Would you like to opt out of marketing communications?",
    "I opt in to receive SMS updates about my application",
    "Opt in for recruiting emails",
    "Do you have a STEM degree?",
    "Preferred contact method",
    "Are you a current employee?",
    "Who is your referral sponsor at the company?",
    "Optional: tell us how you heard about us",
    "Subscribe to our talent community (opt in)",
]
NO_ANSWER = [
    "Will you now or in the future require sponsorship for employment visa status (e.g. H-1B)?",
    "Do you require visa sponsorship?",
    "Will you require sponsorship to work in the United States now or in the future?",
    "Do you require H1B sponsorship?",
    "Will you require H-1B or OPT sponsorship?",
    "Do you need immigration support to work for us?",
    "Do you require employer sponsorship for a work permit?",
]
YES_ANSWER = [
    "Are you authorized to work on an EAD?",
    "Will you require sponsorship beyond your EAD or OPT?",
    "Are you on STEM OPT?",
    "Do you hold F-1 status with OPT work authorization?",
    "Are you working under Optional Practical Training?",
    "Do you require sponsorship for OPT?",
]


@pytest.mark.parametrize("label", NOT_SPONSORSHIP)
def test_marketing_and_unrelated_labels_are_not_sponsorship(label):
    assert not w.is_sponsorship({"key": None, "label": label})
    assert not w.IMMIGRATION_LABEL.search(label)


@pytest.mark.parametrize("label", NO_ANSWER)
def test_sponsorship_wordings_answer_no(label):
    assert w.is_sponsorship({"key": None, "label": label})
    assert w.sponsorship_answer(label) == "No"


@pytest.mark.parametrize("label", YES_ANSWER)
def test_ead_opt_only_wordings_answer_yes(label):
    assert w.is_sponsorship({"key": None, "label": label})
    assert w.sponsorship_answer(label) == "Yes"


def test_key_alone_marks_sponsorship():
    assert w.is_sponsorship({"key": "sponsorship_now", "label": "Anything"})


def test_marketing_opt_in_selection_keeps_proposal_without_overwrite():
    field = {"id": "f1", "key": None, "label": "Opt in to text messages", "proposal": "No"}
    selection = w.selection_for(field)
    assert selection == {"id": "f1", "value": "No"}


def test_sponsorship_selection_overwrites():
    field = {"id": "f2", "key": None, "label": "Do you require visa sponsorship?", "proposal": "Yes"}
    selection = w.selection_for(field)
    assert selection["overwrite"] is True and selection["value"] == "No"
