"""S5: huy hiệu worker trên card. Hàm thuần (worker_badge, org_workers, khoá live, nhãn, ellipsis) và card Tk headless.

Phần Tk tự bỏ qua khi không có Tk display, không cần Tk để chạy phần còn lại.
"""
import random
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

# Import org trước stub tkinter: patch.dict gỡ mọi module import trong lúc stub khỏi sys.modules.
from pet_tracker import org  # noqa: F401

try:
    import tkinter  # noqa: F401
    from pet_tracker.ui import kit, panel
except ImportError:
    # Python không có _tkinter: ui chỉ dùng tk trong thân hàm nên stub đủ để import.
    with mock.patch.dict(sys.modules, tkinter=mock.MagicMock(), **{"tkinter.font": mock.MagicMock()}):
        from pet_tracker.ui import kit, panel


def sub(state, **extra):
    return {"kind": "subagent", "id": "a", "state": state, **extra}


def task(state):
    return {"kind": "bgtask", "id": "t", "state": state}


def session(**over):
    base = {"session_id": "s1", "status": "busy", "model": "claude-opus-4", "effort": None, "cwd": "/repo",
            "git_branch": "main", "name": "x", "entrypoint": "cli", "has_transcript": True,
            "last_activity": 1.0, "git": None, "context_tokens": 10, "context_limit": 100,
            "context_pct": 10.0, "totals": {"messages": 3, "output": 5}, "subagents": 0,
            "state": "idle", "wait_kind": None, "todo": None, "detail": None, "last_msg": None, "tool": None}
    base.update(over)
    return base


def bare_panel(wmap=None):
    """Panel chưa khởi tạo (không Tk): chỉ đặt thuộc tính mà các hàm được test đọc."""
    p = object.__new__(panel.Panel)
    p._wmap = wmap
    return p


class WorkerBadgeTests(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(panel.worker_badge([]), ("", False))

    def test_non_list_input(self):
        for bad in (None, "running", {"kind": "subagent", "state": "running"}, 3):
            with self.subTest(bad=bad):
                self.assertEqual(panel.worker_badge(bad), ("", False))

    def test_single_agent(self):
        self.assertEqual(panel.worker_badge([sub("running")]), ("1 agent", False))

    def test_plural_agents(self):
        self.assertEqual(panel.worker_badge([sub("running"), sub("running")]), ("2 agents", False))

    def test_agent_and_task(self):
        self.assertEqual(panel.worker_badge([sub("running"), task("running")]), ("1 agent · 1 task", False))

    def test_single_task(self):
        self.assertEqual(panel.worker_badge([task("running")]), ("1 task", False))

    def test_tasks_only_plural(self):
        self.assertEqual(panel.worker_badge([task("running"), task("running")]), ("2 tasks", False))

    def test_finished_workers_are_hidden(self):
        ws = [sub("done"), sub("failed"), sub("killed"), task("done"), task("killed"), task("ended")]
        self.assertEqual(panel.worker_badge(ws), ("", False))

    def test_stuck_counts_as_agent_and_warns(self):
        self.assertEqual(panel.worker_badge([sub("stuck"), sub("running")]), ("2 agents", True))

    def test_stuck_only_warns(self):
        self.assertEqual(panel.worker_badge([sub("stuck")]), ("1 agent", True))

    def test_unknown_state_ignored(self):
        self.assertEqual(panel.worker_badge([sub("weird")]), ("", False))
        self.assertEqual(panel.worker_badge([sub("running"), sub("weird")]), ("1 agent", False))

    def test_unknown_kind_ignored(self):
        self.assertEqual(panel.worker_badge([{"kind": "other", "state": "running"}]), ("", False))

    def test_non_dict_items_ignored(self):
        self.assertEqual(panel.worker_badge([None, "running", sub("running")]), ("1 agent", False))


class OrgWorkersTests(unittest.TestCase):
    def test_none_org_returns_none(self):
        self.assertIsNone(panel.org_workers(None))

    def test_empty_tree(self):
        self.assertEqual(panel.org_workers({"projects": []}), {})

    def test_maps_session_to_its_workers(self):
        w1 = sub("running")
        org_tree = {"projects": [
            {"teams": [{"sessions": [
                {"session_id": "a", "workers": [w1]},
                {"session_id": "b", "workers": []},
            ]}]},
            {"teams": [{"sessions": [{"session_id": "c", "workers": [task("done")]}]}]},
        ]}
        self.assertEqual(panel.org_workers(org_tree), {"a": [w1], "b": [], "c": [task("done")]})

    def test_bad_nodes_skipped(self):
        org_tree = {"projects": [
            "junk",
            {"teams": [{"sessions": ["junk", {"workers": [sub("running")]}, {"session_id": "a"}]}]},
        ]}
        self.assertEqual(panel.org_workers(org_tree), {"a": []})


class WorkerCountsTests(unittest.TestCase):
    def test_none_and_empty_list_differ(self):
        self.assertIsNone(panel._worker_counts(None))
        self.assertEqual(panel._worker_counts([]), ())
        self.assertNotEqual(panel._worker_counts(None), panel._worker_counts([]))

    def test_non_list_is_none(self):
        self.assertIsNone(panel._worker_counts({"kind": "subagent"}))

    def test_org_none_and_empty_org_entry_give_different_live_keys(self):
        s = session()
        self.assertNotEqual(panel.Panel._card_key(s, None)[1], panel.Panel._card_key(s, [])[1])


class WorkerLabelTests(unittest.TestCase):
    def test_fallback_without_org(self):
        p = bare_panel(wmap=None)
        self.assertEqual(p._worker_label(session(subagents=2)), ("2 subagent", False))
        self.assertEqual(p._worker_label(session(subagents=0)), ("", False))

    def test_org_present_uses_badge_and_warns(self):
        p = bare_panel(wmap={"s1": [sub("stuck"), task("running")]})
        self.assertEqual(p._worker_label(session(subagents=2)), ("1 agent · 1 task", True))

    def test_org_present_without_live_workers_hides_fallback(self):
        p = bare_panel(wmap={"s1": [sub("done")]})
        self.assertEqual(p._worker_label(session(subagents=1)), ("", False))

    def test_session_missing_from_org_shows_empty_badge(self):
        # org có mặt nhưng không có session này: không quay về nhãn `N subagent` của collector (R5)
        p = bare_panel(wmap={"other": []})
        self.assertEqual(p._worker_label(session(subagents=1)), ("", False))

    def test_fallback_only_when_no_org_at_all(self):
        self.assertEqual(bare_panel(wmap=None)._worker_label(session(subagents=3)), ("3 subagent", False))
        self.assertEqual(bare_panel(wmap={})._worker_label(session(subagents=3)), ("", False))


class CardKeyLiveTests(unittest.TestCase):
    def test_count_change_moves_only_live_part(self):
        s = session()
        before = panel.Panel._card_key(s, [sub("running")])
        after = panel.Panel._card_key(s, [sub("done")])
        self.assertEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])

    def test_stuck_change_moves_live_part(self):
        s = session()
        self.assertNotEqual(panel.Panel._card_key(s, [sub("running")])[1],
                            panel.Panel._card_key(s, [sub("stuck")])[1])

    def test_same_states_same_key(self):
        s = session()
        self.assertEqual(panel.Panel._card_key(s, [sub("running", id="x")]),
                         panel.Panel._card_key(s, [sub("running", id="y")]))

    def test_struct_change_moves_struct_part(self):
        before = panel.Panel._card_key(session(state="idle"), [sub("running")])
        after = panel.Panel._card_key(session(state="run"), [sub("running")])  # struct của card: state, không status
        self.assertNotEqual(before[0], after[0])

    def test_key_does_not_depend_on_panel_state(self):
        # khoá card là hàm thuần của (session, workers): không đọc hay ghi _wmap của panel
        p = bare_panel(wmap="sentinel")
        key = p._card_key(session(), [sub("running")])
        self.assertEqual(p._wmap, "sentinel")
        self.assertEqual(key, panel.Panel._card_key(session(), [sub("running")]))


def _char_width(ch):
    if ch in "​‌́":
        return 0
    return 14 if ord(ch) > 0x2E80 else 6


class FakeFont:
    """measure theo ký tự (không phụ thuộc font thật). Đếm lần gọi và độ dài lớn nhất đã đo;
    vượt `limit` lần gọi thì báo lỗi, để bản O(n^2) không làm test treo."""

    def __init__(self, limit=None):
        self.calls, self.limit, self.max_len = 0, limit, 0

    def measure(self, text):
        self.calls += 1
        self.max_len = max(self.max_len, len(text))
        if self.limit is not None and self.calls > self.limit:
            raise AssertionError("quá nhiều lần đo")
        return sum(_char_width(c) for c in text)


def reference_ellipsis(text, font, max_px):
    """Vòng lặp cắt đuôi gốc: đối chiếu chuẩn cho bản nhị phân."""
    if font.measure(text) <= max_px:
        return text
    while text and font.measure(text + "…") > max_px:
        text = text[:-1]
    return text + "…"


class EllipsisTests(unittest.TestCase):
    def test_randomised_equivalence_with_reference(self):
        rng = random.Random(20261023)
        pool = "abcXYZ 0-_/.中文字​́…"
        for _ in range(400):
            text = "".join(rng.choice(pool) for _ in range(rng.randint(0, 120)))
            font = FakeFont()
            max_px = rng.randint(-3, sum(_char_width(c) for c in text) + 10)
            with self.subTest(text=text, max_px=max_px):
                self.assertEqual(kit.fit_ellipsis(font, text, max_px),
                                 reference_ellipsis(text, FakeFont(), max_px))

    def test_short_fitting_text_unchanged(self):
        self.assertEqual(kit.fit_ellipsis(FakeFont(), "abc", 100), "abc")

    def test_1mb_ascii_returns_fast_and_bounded(self):
        font = FakeFont(limit=200)
        t0 = time.perf_counter()
        out = kit.fit_ellipsis(font, "a" * 1_000_000, 300)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)
        self.assertLessEqual(font.max_len, 501)

    def test_1mb_cjk_returns_fast_and_bounded(self):
        font = FakeFont(limit=200)
        t0 = time.perf_counter()
        out = kit.fit_ellipsis(font, "中" * 1_000_000, 300)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)

    def test_zero_width_1mb_is_still_truncated(self):
        # ký tự rộng 0 px: 500 ký tự đầu đo ra 0 px nên không bị cắt nếu không có trần
        font = FakeFont(limit=200)
        out = kit.fit_ellipsis(font, "​" * 1_000_000, 300)
        self.assertEqual(out, "​" * 499 + "…")
        self.assertLessEqual(font.max_len, 501)

    def test_combining_1mb_is_still_truncated(self):
        out = kit.fit_ellipsis(FakeFont(limit=200), "́" * 1_000_000, 300)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)

    def test_kit_ellipsis_uses_role_font(self):
        fake_kit = SimpleNamespace(f={"meta": FakeFont(limit=200)})
        out = kit.Kit.ellipsis(fake_kit, "a" * 1_000_000, "meta", 300)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)


class EntrypointLabelTests(unittest.TestCase):
    def test_non_string_entrypoint_treated_as_missing(self):
        for raw in (None, ["cli"], {"a": 1}, 5, ("cli",)):
            with self.subTest(raw=raw):
                self.assertEqual(panel.ep_label(raw), "")

    def test_string_entrypoint_mapped(self):
        self.assertEqual(panel.ep_label("cli"), "CLI")
        self.assertEqual(panel.ep_label("unknown-x"), "")


def _tk_root():
    """Tk root đã ẩn, hoặc None khi không có Tk display (test Tk bị bỏ qua)."""
    try:
        import tkinter as real_tk
        from pet_tracker.ui.kit import register_fonts
        register_fonts()  # Archivo trước root đầu tiên của process (Tk chốt danh sách font lúc đó)
        root = real_tk.Tk()
    except Exception:  # thiếu _tkinter hoặc không có display
        return None
    root.withdraw()
    return root


class HeadlessCardTests(unittest.TestCase):
    def setUp(self):
        self.root = _tk_root()
        if self.root is None:
            self.skipTest("không có Tk display")
        self.addCleanup(self.root.destroy)
        import tkinter as real_tk
        from pet_tracker import theme
        self.kit = kit.Kit(self.root, 1.0)
        self.pn = object.__new__(panel.Panel)
        self.pn.app = SimpleNamespace(kit=self.kit, level_color=lambda pct: theme.DARK["ok"],
                                      focus_session=mock.Mock(), menus=mock.Mock())
        self.pn.pw, self.pn.bar_w = 400, 10
        self.pn.cards = {}
        self.pn._wmap = None
        self.P = self.kit.P
        self.parent = real_tk.Frame(self.root)
        self.parent.pack()

    def _card(self, s):
        self.pn._build_card(self.parent, s)
        return self.pn.cards[s["session_id"]][0]

    def test_update_card_switches_warn_colour_and_back(self):
        s = session(subagents=1)
        self.pn._wmap = {"s1": [sub("running")]}
        refs = self._card(s)
        self.assertEqual(refs["workers"].cget("fg"), self.P["mut"])

        self.pn._wmap = {"s1": [sub("stuck")]}
        self.pn._patch_card(s)
        self.assertEqual(refs["workers"].cget("fg"), self.P["warn"])
        self.assertEqual(refs["workers"].cget("text"), "1 agent")

        self.pn._wmap = {"s1": [sub("running")]}
        self.pn._patch_card(s)
        self.assertEqual(refs["workers"].cget("fg"), self.P["mut"])

    def test_badge_label_has_its_own_row(self):
        self.pn._wmap = {"s1": [sub("running")]}
        refs = self._card(session())
        self.assertIsNot(refs["workers"].master, refs["where"].master)

    def test_badge_label_always_built_and_packed_only_with_text(self):
        s = session()
        self.pn._wmap = {"s1": []}
        refs = self._card(s)
        lbl = refs["workers"]
        self.assertEqual(lbl.winfo_manager(), "")  # không có chữ: không pack, không hở dòng

        self.pn._wmap = {"s1": [sub("running")]}
        self.pn._patch_card(s)
        self.assertEqual(lbl.cget("text"), "1 agent")
        self.assertEqual(lbl.winfo_manager(), "pack")

        self.pn._wmap = {"s1": []}
        self.pn._patch_card(s)
        self.assertEqual(lbl.cget("text"), "")
        self.assertEqual(lbl.winfo_manager(), "")

    def test_hostile_1mb_name_card_builds_fast(self):
        t0 = time.perf_counter()
        self._card(session(name="x" * 1_000_000))
        self.assertLess(time.perf_counter() - t0, 2.0)


if __name__ == "__main__":
    unittest.main()
