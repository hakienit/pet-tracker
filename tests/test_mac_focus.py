"""Deep link Claude desktop trên macOS: chỉ host session id đúng charset mới vào URL."""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

# Nạp mac.py trực tiếp: tránh pet_tracker/platform/__init__.py (chọn win/mac theo sys.platform).
_MAC = Path(__file__).resolve().parents[1] / "pet_tracker" / "platform" / "mac.py"
_spec = importlib.util.spec_from_file_location("mac_under_test", _MAC)
mac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mac)

PREFIX = "claude://code/continue?session="
UUID_ID = "local_3f2a9c1e-5b7d-4e8a-9c0d-1a2b3c4d5e6f"


class DeepLinkTests(unittest.TestCase):
    def test_valid_ids_keep_same_link(self):
        self.assertEqual(mac.deep_link(UUID_ID), PREFIX + UUID_ID)
        self.assertEqual(mac.deep_link("local_" + "a" * 64), PREFIX + "local_" + "a" * 64)
        self.assertEqual(mac.deep_link("local_abc-123"), PREFIX + "local_abc-123")

    def test_invalid_ids_give_none(self):
        bad = [
            "local_" + "a" * 65,   # quá 64 ký tự
            "",                    # rỗng
            "local_",              # thiếu phần sau
            "local_x&evil=1",      # chèn tham số
            "local_#a",            # fragment
            "local_a b",           # khoảng trắng
            "local_\n",            # xuống dòng ($ của regex khớp trước \n)
            'local_x"',            # dấu nháy kép
            "loсal_abc",      # Cyrillic с (look-alike)
            "local_аbc",      # Cyrillic а (look-alike)
            "local_x_y",           # underscore: charset Windows không có
        ]
        for host in bad:
            with self.subTest(host=host):
                self.assertIsNone(mac.deep_link(host))

    def test_non_str_gives_none(self):
        self.assertIsNone(mac.deep_link(None))
        self.assertIsNone(mac.deep_link(123))


class FocusSessionTests(unittest.TestCase):
    def _focus(self, host):
        sess = {"entrypoint": "claude-desktop", "host_session_id": host, "pid": 1}
        with mock.patch.object(mac, "open_path") as op, \
                mock.patch.object(mac, "_ps", return_value=""), \
                mock.patch.object(mac, "_ancestor_app", return_value=None):
            result = mac.focus_session(sess)
        return result, op

    def test_valid_id_opens_link(self):
        result, op = self._focus(UUID_ID)
        op.assert_called_once_with(PREFIX + UUID_ID)
        self.assertEqual(result[0], True)

    def test_injected_id_never_reaches_open_path(self):
        for host in ("local_x&evil=1", "local_\nfoo", 'local_x"; do shell'):
            with self.subTest(host=host):
                _, op = self._focus(host)
                op.assert_not_called()


if __name__ == "__main__":
    unittest.main()
