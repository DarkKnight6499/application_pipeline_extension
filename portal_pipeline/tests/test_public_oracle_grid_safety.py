from pathlib import Path

from browser_test_support import SyntheticBrowserTest

EXT = Path(__file__).resolve().parents[1] / "extension"
PAGE = '<input id="b" type="submit" role="combobox" aria-haspopup="grid" aria-controls="p" value="x"><input id="t" role="combobox" aria-haspopup="grid" aria-controls="p">'


class OracleGridSafetyTests(SyntheticBrowserTest):
    def test_submit_input_is_not_a_grid_combobox(self):
        self.open_markup(PAGE)
        self.page.add_script_tag(path=str(EXT / "oracle-grid.js"))
        self.assertEqual(self.page.evaluate("[PortalOracleGrid.matches(document.getElementById('b')), PortalOracleGrid.matches(document.getElementById('t'))]"), [False, True])
