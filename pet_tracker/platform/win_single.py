"""Chỉ cho chạy một bản Wisp mỗi user (Windows named mutex + event).

Bản chạy sau phát hiện mutex đã tồn tại thì bật event "show" rồi thoát; bản đang chạy có một
thread chờ event đó và mở panel lên, nên người dùng thấy ngay widget đang chạy.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import os
import threading

k32 = ctypes.windll.kernel32
k32.CreateMutexW.restype = w.HANDLE
k32.CreateEventW.restype = w.HANDLE
k32.OpenEventW.restype = w.HANDLE

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0


def _names() -> tuple:
    user = "".join(ch for ch in (os.environ.get("USERNAME") or "user") if ch.isalnum()) or "user"
    base = f"Local\\wisp-{user}"
    return base + "-mutex", base + "-show"


class SingleInstance:
    def __init__(self):
        mname, ename = _names()
        self.mutex = k32.CreateMutexW(None, False, mname)
        self.already = k32.GetLastError() == ERROR_ALREADY_EXISTS
        self.event = None
        self._ename = ename
        if not self.already:
            self.event = k32.CreateEventW(None, False, False, ename)  # auto-reset

    def notify_running(self) -> bool:
        """Gọi từ bản chạy sau: nhờ bản đang chạy mở panel."""
        h = k32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, False, self._ename)
        if not h:
            return False
        try:
            return bool(k32.SetEvent(h))
        finally:
            k32.CloseHandle(h)

    def listen(self, on_show) -> None:
        """Bản đang chạy: gọi on_show() (từ thread nền) mỗi khi có bản khác được mở."""
        if not self.event:
            return

        def loop():
            while True:
                if k32.WaitForSingleObject(self.event, 0xFFFFFFFF) == WAIT_OBJECT_0:
                    try:
                        on_show()
                    except Exception:
                        pass

        threading.Thread(target=loop, daemon=True, name="single-instance").start()
