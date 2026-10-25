import workday_run as w


def test_greenhouse_host_and_title(monkeypatch):
    monkeypatch.setitem(w.PORTAL, "greenhouse", True)
    assert w.is_workday_url("https://job-boards.greenhouse.io/acme/jobs/1")
    assert not w.is_workday_url("https://acme.wd5.myworkdayjobs.com/x")
    assert w.step_title(object()) == "greenhouse application form"


def test_greenhouse_upload_skips_when_no_file():
    assert w.greenhouse_upload(object(), "resume", None) is None
