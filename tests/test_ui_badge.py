"""S5: huy hiệu worker trên card. Hàm thuần (worker_badge, org_workers, khoá live, nhãn) và card Tk headless.

Phần Tk tự bỏ qua khi không có Tk display, không cần Tk để chạy phần còn lại.
"""
import random
import sys
import time
import unittest
from unittest import mock

# Import org và queue trước stub tkinter: patch.dict gỡ mọi module import trong lúc stub khỏi sys.modules.
# Nếu queue chưa có sẵn, module test khác (queue.Empty) sẽ lệch lớp với queue mà ui.py đã nạp.
import queue  # noqa: F401
from pet_tracker import org  # noqa: F401

try:
    import tkinter  # noqa: F401
    from pet_tracker import ui
except ImportError:
    # Python không có _tkinter: ui.py chỉ dùng tk trong thân hàm nên stub đủ để import.
    with mock.patch.dict(sys.modules, tkinter=mock.MagicMock(), **{"tkinter.font": mock.MagicMock()}):
        from pet_tracker import ui


def sub(state, **extra):
    return {"kind": "subagent", "id": "a", "state": state, **extra}


def task(state):
    return {"kind": "bgtask", "id": "t", "state": state}


def session(**over):
    base = {"session_id": "s1", "status": "busy", "model": "claude-opus-4", "effort": None, "cwd": "/repo",
            "git_branch": "main", "name": "x", "entrypoint": "cli", "has_transcript": True,
            "last_activity": 1.0, "git": None, "context_tokens": 10, "context_limit": 100,
            "context_pct": 10.0, "totals": {"messages": 3, "output": 5}, "subagents": 0}
    base.update(over)
    return base


def bare_app(wmap=None):
    """PetApp chưa khởi tạo (không Tk): chỉ đặt thuộc tính mà các hàm được test đọc."""
    app = object.__new__(ui.PetApp)
    app._wmap = wmap
    return app


class WorkerBadgeTests(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(ui.worker_badge([]), ("", False))

    def test_non_list_input(self):
        for bad in (None, "running", {"kind": "subagent", "state": "running"}, 3):
            with self.subTest(bad=bad):
                self.assertEqual(ui.worker_badge(bad), ("", False))

    def test_single_agent(self):
        self.assertEqual(ui.worker_badge([sub("running")]), ("1 agent", False))

    def test_plural_agents(self):
        self.assertEqual(ui.worker_badge([sub("running"), sub("running")]), ("2 agents", False))

    def test_agent_and_task(self):
        self.assertEqual(ui.worker_badge([sub("running"), task("running")]), ("1 agent · 1 task", False))

    def test_single_task(self):
        self.assertEqual(ui.worker_badge([task("running")]), ("1 task", False))

    def test_tasks_only_plural(self):
        self.assertEqual(ui.worker_badge([task("running"), task("running")]), ("2 tasks", False))

    def test_finished_workers_are_hidden(self):
        ws = [sub("done"), sub("failed"), sub("killed"), task("done"), task("killed"), task("ended")]
        self.assertEqual(ui.worker_badge(ws), ("", False))

    def test_stuck_counts_as_agent_and_warns(self):
        self.assertEqual(ui.worker_badge([sub("stuck"), sub("running")]), ("2 agents", True))

    def test_stuck_only_warns(self):
        self.assertEqual(ui.worker_badge([sub("stuck")]), ("1 agent", True))

    def test_unknown_state_ignored(self):
        self.assertEqual(ui.worker_badge([sub("weird")]), ("", False))
        self.assertEqual(ui.worker_badge([sub("running"), sub("weird")]), ("1 agent", False))

    def test_unknown_kind_ignored(self):
        self.assertEqual(ui.worker_badge([{"kind": "other", "state": "running"}]), ("", False))

    def test_non_dict_items_ignored(self):
        self.assertEqual(ui.worker_badge([None, "running", sub("running")]), ("1 agent", False))


class OrgWorkersTests(unittest.TestCase):
    def test_none_org_returns_none(self):
        self.assertIsNone(ui.org_workers(None))

    def test_empty_tree(self):
        self.assertEqual(ui.org_workers({"projects": []}), {})

    def test_maps_session_to_its_workers(self):
        w1 = sub("running")
        org_tree = {"projects": [
            {"teams": [{"sessions": [
                {"session_id": "a", "workers": [w1]},
                {"session_id": "b", "workers": []},
            ]}]},
            {"teams": [{"sessions": [{"session_id": "c", "workers": [task("done")]}]}]},
        ]}
        self.assertEqual(ui.org_workers(org_tree), {"a": [w1], "b": [], "c": [task("done")]})

    def test_bad_nodes_skipped(self):
        org_tree = {"projects": [
            "junk",
            {"teams": [{"sessions": ["junk", {"workers": [sub("running")]}, {"session_id": "a"}]}]},
        ]}
        self.assertEqual(ui.org_workers(org_tree), {"a": []})


class WorkerCountsTests(unittest.TestCase):
    def test_none_and_empty_list_differ(self):
        self.assertIsNone(ui._worker_counts(None))
        self.assertEqual(ui._worker_counts([]), ())
        self.assertNotEqual(ui._worker_counts(None), ui._worker_counts([]))

    def test_non_list_is_none(self):
        self.assertIsNone(ui._worker_counts({"kind": "subagent"}))

    def test_org_none_and_empty_org_entry_give_different_live_keys(self):
        s = session()
        self.assertNotEqual(ui.PetApp._card_key(s, None)[1], ui.PetApp._card_key(s, [])[1])


class WorkerLabelTests(unittest.TestCase):
    def test_fallback_without_org(self):
        app = bare_app(wmap=None)
        self.assertEqual(app._worker_label(session(subagents=2)), ("  ·  2 subagent", False))
        self.assertEqual(app._worker_label(session(subagents=0)), ("", False))

    def test_org_present_uses_badge_and_warns(self):
        app = bare_app(wmap={"s1": [sub("stuck"), task("running")]})
        self.assertEqual(app._worker_label(session(subagents=2)), ("  ·  1 agent · 1 task", True))

    def test_org_present_without_live_workers_hides_fallback(self):
        app = bare_app(wmap={"s1": [sub("done")]})
        self.assertEqual(app._worker_label(session(subagents=1)), ("", False))

    def test_session_missing_from_org_falls_back(self):
        app = bare_app(wmap={"other": []})
        self.assertEqual(app._worker_label(session(subagents=1)), ("  ·  1 subagent", False))


class CardKeyLiveTests(unittest.TestCase):
    def test_count_change_moves_only_live_part(self):
        s = session()
        before = ui.PetApp._card_key(s, [sub("running")])
        after = ui.PetApp._card_key(s, [sub("done")])
        self.assertEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])

    def test_stuck_change_moves_live_part(self):
        s = session()
        self.assertNotEqual(ui.PetApp._card_key(s, [sub("running")])[1],
                            ui.PetApp._card_key(s, [sub("stuck")])[1])

    def test_same_states_same_key(self):
        s = session()
        self.assertEqual(ui.PetApp._card_key(s, [sub("running", id="x")]),
                         ui.PetApp._card_key(s, [sub("running", id="y")]))

    def test_struct_change_moves_struct_part(self):
        before = ui.PetApp._card_key(session(), [sub("running")])
        after = ui.PetApp._card_key(session(status="idle"), [sub("running")])
        self.assertNotEqual(before[0], after[0])

    def test_fallback_without_org_tracks_subagents(self):
        before = ui.PetApp._card_key(session(subagents=1), None)
        after = ui.PetApp._card_key(session(subagents=2), None)
        self.assertEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])


class SignatureSideEffectTests(unittest.TestCase):
    def test_signature_does_not_touch_wmap(self):
        app = bare_app(wmap="sentinel")
        app._update = None
        app._update_busy = None
        app.cfg = {}
        app._closed_list = lambda: []
        snap = {"sessions": [], "local": {}, "quota": {}, "org": {"projects": []}}
        app._signature(snap)
        self.assertEqual(app._wmap, "sentinel")


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
                self.assertEqual(bare_app()._ellipsis(text, font, max_px),
                                 reference_ellipsis(text, FakeFont(), max_px))

    def test_short_fitting_text_unchanged(self):
        self.assertEqual(bare_app()._ellipsis("abc", FakeFont(), 100), "abc")

    def test_1mb_ascii_returns_fast_and_bounded(self):
        font = FakeFont(limit=200)
        t0 = time.perf_counter()
        out = bare_app()._ellipsis("a" * 1_000_000, font, 300)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)
        self.assertLessEqual(font.max_len, 501)

    def test_1mb_cjk_returns_fast_and_bounded(self):
        font = FakeFont(limit=200)
        t0 = time.perf_counter()
        out = bare_app()._ellipsis("中" * 1_000_000, font, 300)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)

    def test_zero_width_1mb_is_still_truncated(self):
        # ký tự rộng 0 px: 500 ký tự đầu đo ra 0 px nên không bị cắt nếu không có trần
        font = FakeFont(limit=200)
        out = bare_app()._ellipsis("​" * 1_000_000, font, 300)
        self.assertEqual(out, "​" * 499 + "…")
        self.assertLessEqual(font.max_len, 501)

    def test_combining_1mb_is_still_truncated(self):
        out = bare_app()._ellipsis("́" * 1_000_000, FakeFont(limit=200), 300)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 500)

    def test_fit_stats_1mb_entrypoint_fast(self):
        app = bare_app()
        app.S = 1
        app.f_xs = app.f_xsb = FakeFont(limit=200)
        s = session(entrypoint="x" * 1_000_000)
        refs = {"fit": (300, "● Rảnh")}
        t0 = time.perf_counter()
        out = app._fit_stats(refs, s)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertTrue(out.endswith("…"))


class CardStatsEntrypointTests(unittest.TestCase):
    def test_non_string_entrypoint_treated_as_missing(self):
        expected = ui.PetApp._card_stats(session(entrypoint=None))
        for raw in (["cli"], {"a": 1}, 5, ("cli",)):
            with self.subTest(raw=raw):
                self.assertEqual(ui.PetApp._card_stats(session(entrypoint=raw)), expected)

    def test_string_entrypoint_mapped(self):
        self.assertIn("CLI", ui.PetApp._card_stats(session(entrypoint="cli")))


def _tk_root():
    """Tk root đã ẩn, hoặc None khi không có Tk display (test Tk bị bỏ qua)."""
    try:
        import tkinter as real_tk
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
        app = bare_app()
        app.root = self.root
        app.S = 1
        app.cfg = {"warn_percent": 70, "danger_percent": 90}
        app._img_cache = {}
        app._init_fonts()  # đúng font của app, để đo chữ khớp với lúc chạy thật
        self.app = app
        self.parent = real_tk.Frame(self.root)
        self.parent.pack()

    def test_stats_fit_beside_status_and_time(self):
        # cw 257 px = panel 320 px (xem _build_session_card): trạng thái + số liệu + thời gian phải vừa
        cw = 257
        s = session(totals={"messages": 1234567, "output": 56000}, entrypoint="cli", subagents=0,
                    last_activity=1.0)
        self.app._wmap = {"s1": []}
        card, _ = self.app._build_session_card(self.parent, s, 0, cw + 29)
        refs = card._refs
        f = self.app.f_xs
        used = (self.app.f_xsb.measure(refs["fit"][1]) + f.measure(refs["stats"].cget("text"))
                + f.measure(refs["ago"].cget("text")) + 16)
        self.assertLessEqual(used, refs["fit"][0])
        self.assertEqual(refs["fit"][0], cw)

    def test_update_card_switches_warn_colour_and_back(self):
        s = session(subagents=1)
        self.app._wmap = {"s1": [sub("running")]}
        card, _ = self.app._build_session_card(self.parent, s, 0, 300)
        refs = card._refs
        self.assertEqual(refs["workers"].cget("fg"), ui.MUTED)

        self.app._wmap = {"s1": [sub("stuck")]}
        self.app._update_card(card, s)
        self.assertEqual(refs["workers"].cget("fg"), ui.YELLOW)
        self.assertEqual(refs["workers"].cget("text"), "  ·  1 agent")

        self.app._wmap = {"s1": [sub("running")]}
        self.app._update_card(card, s)
        self.assertEqual(refs["workers"].cget("fg"), ui.MUTED)

    def test_badge_label_has_its_own_row(self):
        self.app._wmap = {"s1": [sub("running")]}
        card, _ = self.app._build_session_card(self.parent, session(), 0, 300)
        refs = card._refs
        self.assertIsNot(refs["workers"].master, refs["stats"].master)

    def test_badge_label_always_built_and_packed_only_with_text(self):
        s = session()
        self.app._wmap = {"s1": []}
        card, _ = self.app._build_session_card(self.parent, s, 0, 300)
        lbl = card._refs["workers"]
        self.assertIn("workers", card._refs)
        self.assertEqual(lbl.winfo_manager(), "")  # không có chữ: không pack, không hở dòng

        self.app._wmap = {"s1": [sub("running")]}
        self.app._update_card(card, s)
        self.assertEqual(lbl.cget("text"), "  ·  1 agent")
        self.assertEqual(lbl.winfo_manager(), "pack")

        self.app._wmap = {"s1": []}
        self.app._update_card(card, s)
        self.assertEqual(lbl.cget("text"), "")
        self.assertEqual(lbl.winfo_manager(), "")


if __name__ == "__main__":
    unittest.main()
