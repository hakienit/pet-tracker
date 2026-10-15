"""Windows: gõ phím vào console của một process (AttachConsole + WriteConsoleInputW).

Dùng cho action gửi slash command (/model, /effort, /compact, /clear, /exit) vào session Claude Code
CLI. Hoạt động với Windows Terminal (ConPTY) và conhost.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w

k32 = ctypes.windll.kernel32

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE = ctypes.c_void_p(-1).value
KEY_EVENT = 1
VK_RETURN = 0x0D


# ---------------------------------------------------------------- console input
class _KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [("bKeyDown", w.BOOL), ("wRepeatCount", w.WORD), ("wVirtualKeyCode", w.WORD),
                ("wVirtualScanCode", w.WORD), ("uChar", w.WCHAR), ("dwControlKeyState", w.DWORD)]


class _EVENT_UNION(ctypes.Union):
    _fields_ = [("KeyEvent", _KEY_EVENT_RECORD), ("_pad", ctypes.c_byte * 16)]


class _INPUT_RECORD(ctypes.Structure):
    _fields_ = [("EventType", w.WORD), ("Event", _EVENT_UNION)]


def _key_records(text: str) -> list:
    recs = []
    for ch in text:
        vk = VK_RETURN if ch == "\r" else 0
        for down in (True, False):
            r = _INPUT_RECORD()
            r.EventType = KEY_EVENT
            ke = r.Event.KeyEvent
            ke.bKeyDown = down
            ke.wRepeatCount = 1
            ke.wVirtualKeyCode = vk
            ke.wVirtualScanCode = 0x1C if vk == VK_RETURN else 0
            ke.uChar = ch
            ke.dwControlKeyState = 0
            recs.append(r)
    return recs


def type_into_console(pid: int, text: str) -> tuple:
    """Gõ `text` vào console của process pid. Trả (ok, message)."""
    had_console = bool(k32.GetConsoleWindow())
    k32.FreeConsole()
    try:
        if not k32.AttachConsole(int(pid)):
            return False, f"không gắn được vào console của pid {pid} (lỗi {k32.GetLastError()})"
        try:
            k32.SetConsoleCtrlHandler(None, True)
            k32.CreateFileW.restype = w.HANDLE
            h = k32.CreateFileW("CONIN$", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                None, OPEN_EXISTING, 0, None)
            if not h or h == INVALID_HANDLE:
                return False, "không mở được CONIN$"
            try:
                recs = _key_records(text)
                arr = (_INPUT_RECORD * len(recs))(*recs)
                written = w.DWORD()
                ok = k32.WriteConsoleInputW(w.HANDLE(h), arr, len(recs), ctypes.byref(written))
                if not ok or written.value != len(recs):
                    return False, f"WriteConsoleInput lỗi ({written.value}/{len(recs)})"
                return True, "đã gửi"
            finally:
                k32.CloseHandle(w.HANDLE(h))
        finally:
            k32.FreeConsole()
    finally:
        if had_console:
            k32.AttachConsole(0xFFFFFFFF)
