import json

import apply as a


def test_portal_for_hosts():
    assert a.portal_for("https://citi.wd5.myworkdayjobs.com/x") == "workday"
    assert a.portal_for("https://jpmc.fa.oraclecloud.com/hcmUI/x") == "oracle"
    assert a.portal_for("https://career-schwab.icims.com/jobs/1/x/job") == "icims"
    assert a.portal_for("https://jobs.lever.co/acme/1") == "lever"
    assert a.portal_for("https://example.com/job") is None


def test_find_files_prefers_docx_and_first_cover(tmp_path):
    for name in ("Yazad_Madan.docx", "Yazad_Madan.pdf", "CoverLetter_B.docx", "CoverLetter_A.docx", "JD_x.docx"):
        (tmp_path / name).write_text("x")
    resume, cover = a.find_files(tmp_path)
    assert (resume.name, cover.name) == ("Yazad_Madan.docx", "CoverLetter_A.docx")


def test_missing_files_are_none(tmp_path):
    assert a.find_files(tmp_path) == (None, None)


def test_apply_json_supplies_url_and_overrides_files(tmp_path):
    (tmp_path / "Yazad_Madan.docx").write_text("x")
    (tmp_path / "apply.json").write_text(json.dumps({"url": "https://jobs.lever.co/acme/1", "cover": str(tmp_path / "C.docx")}))
    job = a.resolve(None, tmp_path)
    assert job["portal"] == "lever" and job["resume"].name == "Yazad_Madan.docx" and job["cover"].name == "C.docx"
    assert a.driver_args(job)[:2] == ["--portal", "lever"]


def test_unknown_host_stops():
    try:
        a.resolve("https://example.com/job", None)
    except SystemExit as stop:
        assert "No adapter" in str(stop)
    else:
        raise AssertionError("expected SystemExit")
