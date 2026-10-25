import workday_run as w


def test_oracle_skips_history_row_adding(monkeypatch):
    monkeypatch.setitem(w.PORTAL, "oracle", True)
    monkeypatch.setattr(w, "has_heading", lambda *a: (_ for _ in ()).throw(AssertionError("must not look for headings")))
    assert w.ensure_rows(object(), {"employment": [1], "education": [1]}) is True
