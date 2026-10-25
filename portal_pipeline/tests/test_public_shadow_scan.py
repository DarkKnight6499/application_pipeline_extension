"""Synthetic open-shadow coverage; live portal compatibility is unverified."""
from browser_test_support import SyntheticBrowserTest

# Test configuration
LIGHT_FIELDS = '''
<label for="first">First Name</label><input id="first" name="firstName">
<label for="region">Region</label><select id="region" name="region">
<option value="">Choose</option><option value="north">North</option></select>
'''
SHADOW_PAGE = '''<spl-wrapper id="wrapper"></spl-wrapper><script>
customElements.define("spl-wrapper", class extends HTMLElement {
  connectedCallback() {
    this.attachShadow({mode: "open"}).innerHTML = `<spl-form-field></spl-form-field>`;
  }
});
customElements.define("spl-form-field", class extends HTMLElement {
  connectedCallback() {
    this.attachShadow({mode: "open"}).innerHTML = `FIELDS`;
  }
});
</script>'''.replace("FIELDS", LIGHT_FIELDS)


class ShadowScanTests(SyntheticBrowserTest):
    def form_fields(self):
        return [field for field in self.scan() if not field["structure"]["dom_id"].startswith("guard-")]

    def test_nested_open_shadow_scan_and_selected_fill(self):
        self.open_markup(SHADOW_PAGE)
        fields = self.form_fields()
        self.assertEqual([(field["label"], field["type"]) for field in fields],
                         [("First Name", "text"), ("Region", "select-one")])
        result = self.fill([{"id": fields[0]["id"], "value": "Synthetic"}])[0]
        self.assertEqual(result["status"], "filled", result)
        self.assertEqual(self.page.evaluate('''() => document.querySelector("spl-wrapper")
            .shadowRoot.querySelector("spl-form-field").shadowRoot.querySelector("input").value'''), "Synthetic")
        self.assertEqual(self.page.locator("#region").input_value(), "")

    def test_light_dom_scan_is_identical_with_shadow_equivalent(self):
        self.open_markup(LIGHT_FIELDS)
        expected = self.scan()
        self.assertEqual([(field["label"], field["structure"]["dom_id"]) for field in expected[:2]],
                         [("First Name", "first"), ("Region", "region")])
        self.open_markup(SHADOW_PAGE)
        self.assertEqual(self.scan(), expected)

    def test_shadow_labels_use_local_root_and_component_fallbacks(self):
        self.open_markup('''<span id="title">Wrong label</span><spl-form-field label="Phone"></spl-form-field>
        <spl-form-field><span slot="label">City</span></spl-form-field>
        <spl-form-field><span slot="label">Email</span></spl-form-field><script>
        const hosts = document.querySelectorAll("spl-form-field");
        hosts[0].attachShadow({mode: "open"}).innerHTML = '<input name="phone">';
        hosts[1].attachShadow({mode: "open"}).innerHTML = '<slot name="label"></slot><input name="city">';
        hosts[2].attachShadow({mode: "open"}).innerHTML = '<span id="title">Local email</span><input aria-labelledby="title" name="email">';
        </script>''')
        self.assertEqual([field["label"] for field in self.form_fields()], ["Phone", "City", "Local email"])

    def test_shadow_order_depth_closed_roots_and_hidden_controls(self):
        self.open_markup('''<label>Before<input name="before"></label><spl-wrapper></spl-wrapper>
        <label>After<input name="after"></label><script>
        let host = document.querySelector("spl-wrapper");
        for (let depth = 1; depth <= 7; depth++) {
          const root = host.attachShadow({mode: "open"});
          root.innerHTML = '<input aria-label="Level ' + depth + '" name="level' + depth + '"><spl-wrapper></spl-wrapper>';
          host = root.querySelector("spl-wrapper");
        }
        const root = document.querySelector("spl-wrapper").shadowRoot;
        root.insertAdjacentHTML("beforeend", '<input type="hidden" name="hidden"><input name="honeypot"><input hidden name="invisible"><spl-closed></spl-closed>');
        root.querySelector("spl-closed").attachShadow({mode: "closed"}).innerHTML = '<input name="closed">';
        </script>''')
        fields = self.form_fields()
        self.assertEqual([field["structure"]["name"] for field in fields if not field["blocked"]],
                         ["before", "level1", "level2", "level3", "level4", "level5", "level6", "after"])
        self.assertTrue(next(field for field in fields if field["structure"]["name"] == "honeypot")["blocked"])
