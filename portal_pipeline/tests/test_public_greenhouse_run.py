import workday_run as w


def test_single_page_host_and_title(monkeypatch):
    monkeypatch.setitem(w.PORTAL, "single", True)
    monkeypatch.setitem(w.PORTAL, "host", "greenhouse.io")
    assert w.is_workday_url("https://job-boards.greenhouse.io/acme/jobs/1")
    assert not w.is_workday_url("https://acme.wd5.myworkdayjobs.com/x")
    assert w.step_title(object()) == "single page application form"
