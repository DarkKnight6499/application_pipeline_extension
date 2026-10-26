import pytest

import workday_run as w

CHANGED = "The visible form structure changed. Stop and rescan before filling more fields."


class FakePage:
    def __init__(self, script_results):
        self.script_results = list(script_results)

    def evaluate(self, script, arg=None):
        return self.script_results.pop(0)


def field(label, current=""):
    return {"id": label, "label": label, "key": None, "status": "prepared", "proposal": "x", "blocked": False,
            "type": "text", "disabled": False, "current": current, "required": False}


def setup(monkeypatch, scans):
    monkeypatch.setattr(w, "ensure_rows", lambda page, profile: True)
    monkeypatch.setattr(w, "bind_rows", lambda page, profile: {})
    monkeypatch.setattr(w, "plain_workday", lambda: True)
    monkeypatch.setattr(w, "require_writable_step", lambda page: None)
    monkeypatch.setattr(w, "ROW_SETTLE_SECONDS", 0)
    monkeypatch.setattr(w, "scan", lambda page, profile, bindings=None: scans.pop(0))


def test_structure_abort_after_a_fill_rescans_and_continues(monkeypatch):
    a, b = field("A"), field("B")
    scans = [[a, b], [field("A", "x"), b], [field("A", "x"), field("B", "x")]]
    setup(monkeypatch, scans)
    page = FakePage([[{"id": "A", "status": "filled"}, {"id": "B", "status": "failed", "message": CHANGED}],
                     [{"id": "B", "status": "filled"}]])
    w.run_page(page, {}, False, {})
    assert not page.script_results


def test_other_failures_still_stop(monkeypatch):
    setup(monkeypatch, [[field("A"), field("B")]])
    page = FakePage([[{"id": "A", "status": "filled"}, {"id": "B", "status": "failed", "message": "No exact search result matched."}]])
    with pytest.raises(w.DriverFailed):
        w.run_page(page, {}, False, {})


def test_structure_abort_without_progress_stops_after_rescan(monkeypatch):
    setup(monkeypatch, [[field("A")], [field("A")]])
    page = FakePage([[{"id": "A", "status": "failed", "message": CHANGED}]])
    with pytest.raises(w.DriverFailed):
        w.run_page(page, {}, False, {})
