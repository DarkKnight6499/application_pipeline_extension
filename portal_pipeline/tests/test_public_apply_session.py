import hashlib
import json

import pytest

import apply as a
import workday_run as w


def session(tmp_path, **extra):
    resume = tmp_path / "Yazad_Madan.docx"
    resume.write_bytes(b"resume bytes")
    data = {"session": True, "url": "https://citi.wd5.myworkdayjobs.com/x", "resume": str(resume),
            "resume_sha256": hashlib.sha256(b"resume bytes").hexdigest(), "cover": None, **extra}
    (tmp_path / "_inputs").mkdir()
    (tmp_path / "_inputs" / "apply.json").write_text(json.dumps(data))
    return resume


def test_session_in_inputs_is_read(tmp_path):
    session(tmp_path)
    job = a.resolve(None, tmp_path)
    assert job["portal"] == "workday" and job["resume"].name == "Yazad_Madan.docx"


def test_hash_mismatch_stops(tmp_path):
    resume = session(tmp_path)
    resume.write_bytes(b"changed")
    with pytest.raises(SystemExit, match="SHA-256"):
        a.resolve(None, tmp_path)


def test_session_without_cover_never_picks_one_from_folder(tmp_path):
    session(tmp_path)
    (tmp_path / "CoverLetter_X.docx").write_text("x")
    assert a.resolve(None, tmp_path)["cover"] is None


def test_session_names_cover_exactly(tmp_path):
    cover = tmp_path / "CoverLetter_A.docx"
    cover.write_text("x")
    session(tmp_path, cover=str(cover))
    assert a.resolve(None, tmp_path)["cover"] == cover


@pytest.mark.parametrize("label,expected", [
    ("Will you now or in the future require H-1B sponsorship?", "No"),
    ("Do you require sponsorship for H1B now or in the future?", "No"),
    ("Do you require EAD or OPT sponsorship?", "Yes"),
    ("Will you require STEM OPT support?", "Yes"),
    ("Do you require employment authorization sponsorship?", "Yes"),
    ("Do you require visa sponsorship?", "No"),
    ("Do you require H-1B or OPT sponsorship?", "No"),
    (None, "No"),
])
def test_sponsorship_answer_rule(label, expected):
    assert w.sponsorship_answer(label) == expected
