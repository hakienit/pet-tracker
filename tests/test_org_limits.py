"""Giới hạn an toàn của org (F1, F5a): số quá lớn không làm hỏng cây; chuỗi dài được cắt trước khi lọc ký tự."""
import random
import time
import unittest
from unittest import mock

from pet_tracker import org

NOW = 10_000.0
CFG = {"agent_prefixes": ["les-"], "stuck_after_sec": 120}


def sess(sid="s1", **kw):
    s = {"session_id": sid, "started_at": 1000.0, "cwd": "/r", "name": "n", "status": "busy",
         "git": {"top": "/r", "common": "/r/.git", "branch": "main"}, "agent_calls": [], "workers": []}
    s.update(kw)
    return s


def sub(wid, **kw):
    w = {"kind": "subagent", "id": wid, "tool_use_id": "tu-" + wid, "agent_type": "les-engineering",
         "description": "d", "depth": 1, "finished": False, "notif_status": None, "mtime": NOW - 10,
         "started": NOW - 100, "last_activity": NOW - 10, "tokens": 5, "open_tools": 0, "agent_calls": []}
    w.update(kw)
    return w


def session_ids(tree):
    return sorted(s["session_id"] for p in tree["projects"] for t in p["teams"] for s in t["sessions"])


class _Spy:
    """Thay org._CTRL: ghi độ dài chuỗi mà regex phải quét, rồi đi qua regex thật."""

    def __init__(self, real):
        self.real, self.seen = real, []

    def sub(self, repl, text):
        self.seen.append(len(text))
        return self.real.sub(repl, text)


class HugeNumberTest(unittest.TestCase):
    def test_num_huge_int_is_none(self):
        self.assertIsNone(org._num(10 ** 400))
        self.assertIsNone(org._num(-(10 ** 400)))
        self.assertEqual(org._num(1.5), 1.5)

    def test_huge_numbers_keep_rest_of_tree(self):
        bad = sess("a", started_at=10 ** 400, workers=[
            sub("A", started=10 ** 400, last_activity=10 ** 400, mtime=10 ** 400, tokens=10 ** 400)])
        tree = org.build([bad, sess("b")], CFG, NOW)
        self.assertEqual(session_ids(tree), ["a", "b"])


class StringCutTest(unittest.TestCase):
    def test_long_string_is_cut_before_filtering(self):
        spy = _Spy(org._CTRL)
        with mock.patch.object(org, "_CTRL", spy):
            out = org._s("a" * 1_000_000)
        self.assertEqual(out, "a" * org.MAX_STR)
        self.assertLessEqual(max(spy.seen), org.MAX_STR * 8)

    def test_one_megabyte_control_string_is_fast(self):
        t0 = time.perf_counter()
        out = org._s("\x01" * 1_000_000 + "tail")
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertEqual(out, "")

    def test_same_output_as_full_filter_for_strings_up_to_cut(self):
        rng = random.Random(20261023)
        pool = "ab \x01\x7f​‮đ中"
        for _ in range(300):
            v = "".join(rng.choice(pool) for _ in range(rng.randint(0, org.MAX_STR * 8)))
            with self.subTest(v=v[:40]):
                self.assertEqual(org._s(v), org._CTRL.sub("", v)[:org.MAX_STR])


if __name__ == "__main__":
    unittest.main()
