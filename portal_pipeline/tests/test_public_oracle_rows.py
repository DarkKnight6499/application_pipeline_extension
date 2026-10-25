import workday_run as w


def test_oracle_skips_history_row_adding(monkeypatch):
    monkeypatch.setitem(w.PORTAL, "oracle", True)
    monkeypatch.setattr(w, "has_heading", lambda *a: (_ for _ in ()).throw(AssertionError("must not look for headings")))
    assert w.ensure_rows(object(), {"employment": [1], "education": [1]}) is True


from browser_test_support import SyntheticBrowserTest


class NativeDialogTests(SyntheticBrowserTest):
    def test_native_open_dialog_counts(self):
        self.open_markup("<dialog open><p>Sure?</p></dialog>")
        self.assertTrue(w.dialog_open(self.page))


def test_us_state_location_maps_to_united_states():
    import oracle_history as h
    assert h.plan(["x"], {"education": [{"school": "Rutgers", "location": "Newark, NJ"}]}) == [("education", 0)]


class CookieDialogTests(SyntheticBrowserTest):
    def test_cookie_banner_is_not_a_blocking_dialog(self):
        self.open_markup('<div role="dialog">We use cookies</div>')
        self.assertFalse(w.dialog_open(self.page))
