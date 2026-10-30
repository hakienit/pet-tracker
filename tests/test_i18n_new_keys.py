"""Keys added for the Board tab and the 3D viewer (plan slice S1b)."""
import re
import unittest

from pet_tracker import i18n

# Placeholders allowed per Board key (spec board rev 4, section "Cấu hình").
BOARD_KEYS = {
    "cr.tab.tree": set(), "cr.tab.board": set(), "cr.board.floor": {"i", "n"},
    "cr.board.more_desks": {"n"}, "cr.board.more_detail": set(), "cr.board.hint": set(),
    "cr.board.nodata": set(), "cr.f.workers": set(),
    "cr.board.cap": {"n"}, "cr.board.stuck_desks": {"n"},  # detail of the "+N desks" chip
}
# App-side viewer keys (spec viewer rev 6, section "Lối vào UI"); never sent to the browser.
APP_KEYS = ("isl.view3d", "isl.view3d.sub", "v3d.open_fail", "v3d.link_copied")
# Closed list of 39 page keys (spec viewer rev 6, section "Trang"), without the "v3d.page." prefix.
# S3a-1 compares viewer.PAGE_STRING_KEYS against this list.
PAGE_NAMES = (
    "title", "reset", "loading",
    "status.nodes", "status.hidden", "status.more_desks", "status.stuck_desks",
    "banner.stale", "banner.expired", "banner.disconnected", "banner.schema", "retry",
    "reason.no_data", "reason.layout_error", "reason.too_large", "reason.generic",
    "webgl.missing", "webgl.lost",
    "kind.project", "kind.team", "kind.session", "kind.subagent", "kind.bgtask", "kind.overflow",
    "state.idle", "state.run", "state.wait", "state.done",
    "state.running", "state.stuck", "state.failed", "state.killed", "state.ended", "state.unknown",
    "detail.kind", "detail.label", "detail.sub", "detail.state", "detail.tokens",
)
PAGE_N = {"status.nodes", "status.hidden", "status.more_desks", "status.stuck_desks", "banner.stale"}
PAGE_PREFIX = "v3d.page."


def holes(s):
    return set(re.findall(r"{(\w+)}", s))


class NewKeys(unittest.TestCase):
    def test_page_list_is_39_unique(self):
        self.assertEqual(len(PAGE_NAMES), 39)
        self.assertEqual(len(set(PAGE_NAMES)), 39)

    def test_board_keys(self):
        for table in (i18n.VI, i18n.EN):
            for k, ph in BOARD_KEYS.items():
                self.assertIn(k, table, k)
                self.assertTrue(table[k].strip(), k)
                self.assertEqual(holes(table[k]), ph, k)

    def test_app_keys(self):
        for table in (i18n.VI, i18n.EN):
            for k in APP_KEYS:
                self.assertIn(k, table, k)
                self.assertTrue(table[k].strip(), k)
                self.assertEqual(holes(table[k]), set(), k)
        self.assertEqual(i18n.VI["isl.view3d"], "3D office")
        self.assertEqual(i18n.EN["isl.view3d"], "3D office")

    def test_page_keys_exact(self):
        want = {PAGE_PREFIX + n for n in PAGE_NAMES}
        for table in (i18n.VI, i18n.EN):
            have = {k for k in table if k.startswith(PAGE_PREFIX)}
            self.assertEqual(have - want, set(), "extra v3d.page.* keys")
            self.assertEqual(want - have, set(), "missing v3d.page.* keys")

    def test_page_values_and_placeholders(self):
        for table in (i18n.VI, i18n.EN):
            for n in PAGE_NAMES:
                v = table[PAGE_PREFIX + n]
                self.assertIsInstance(v, str)
                self.assertTrue(v.strip(), n)
                self.assertEqual(holes(v), {"n"} if n in PAGE_N else set(), n)


if __name__ == "__main__":
    unittest.main()
