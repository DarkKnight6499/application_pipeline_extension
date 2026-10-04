"""Page-level CAPTCHA gate fires only on a visible challenge, on fabricated pages."""
from browser_test_support import SyntheticBrowserTest

# Synthetic gate configuration
FIELD = '<label>First name<input id="first"></label>'
RECAPTCHA = "https://www.google.com/recaptcha/api2/"
CASES = [
    ("hidden_display_none", FIELD + f'<iframe src="{RECAPTCHA}bframe" style="display:none"></iframe>', None),
    ("hidden_visibility", FIELD + f'<iframe src="{RECAPTCHA}bframe" style="visibility:hidden"></iframe>', None),
    ("zero_opacity", FIELD + f'<iframe src="{RECAPTCHA}bframe" style="opacity:0"></iframe>', None),
    ("offscreen", FIELD + f'<iframe src="{RECAPTCHA}bframe" style="position:absolute;left:-9999px"></iframe>', None),
    ("hidden_parent", FIELD + f'<div hidden><iframe src="{RECAPTCHA}bframe"></iframe></div>', None),
    ("invisible_badge", FIELD + f'<div class="grecaptcha-badge" style="position:fixed;right:0;bottom:0;width:70px;height:60px"><iframe src="{RECAPTCHA}anchor" style="width:70px;height:60px"></iframe></div>', None),
    ("visible_challenge", FIELD + f'<iframe src="{RECAPTCHA}bframe" style="width:300px;height:200px"></iframe>', "captcha"),
    ("visible_turnstile", FIELD + '<div class="cf-turnstile" style="width:300px;height:65px"></div>', "captcha"),
    ("hidden_turnstile", FIELD + '<div class="cf-turnstile" style="display:none"></div>', None),
]


class PublicCaptchaGateTests(SyntheticBrowserTest):
    def test_gate_fires_only_on_visible_challenge(self):
        for name, markup, kind in CASES:
            with self.subTest(case=name):
                self.open_markup(markup)
                gate = self.page.evaluate("PortalAdapters.forLocation(location.href).humanGate(document)")
                self.assertEqual(gate and gate["kind"], kind)
                first = next(field for field in self.scan() if field["key"] == "first_name")
                status = self.fill([{"id": first["id"], "value": "Synthetic"}])[0]["status"]
                self.assertEqual(status, "blocked_by_human_gate" if kind else "filled")
                self.assertEqual(self.page.locator("#first").input_value(), "" if kind else "Synthetic")
