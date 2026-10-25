import workday_run as w


def test_every_sponsorship_value_is_no(monkeypatch):
    monkeypatch.setattr(w, "resolve_profile", lambda root: {"values": {"sponsorship_future": {"value": "Yes", "source": "x"}}})
    monkeypatch.setattr(w.answer_memory, "load_memory", lambda *a, **k: {"answers": {}, "consents": {}, "aliases": {}})
    monkeypatch.setattr(w.picker_aliases, "profile_pickers", lambda *a, **k: {})
    values = w.build_profile()["values"]
    assert {values[key]["value"] for key in w.SPONSORSHIP_KEYS} == {"No"}
