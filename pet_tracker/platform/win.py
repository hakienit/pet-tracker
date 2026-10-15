"""Cài đặt interface nền tảng cho Windows (Win32 qua ctypes, registry qua winreg)."""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import win_autostart as _auto
from . import win_focus as _focus
from .win_single import SingleInstance
from .win_update import launch_swap

__all__ = [
    "NAME", "GLOBAL_MOUSE", "CAN_SELF_UPDATE", "RIGHT_CLICK_EVENTS",
    "init_process", "dpi_scale", "work_area", "cursor_pos", "mouse_down", "transparent_key",
    "make_transparent", "round_corners", "state_dir", "open_path", "process_alive", "read_credentials",
    "focus_session", "open_terminal", "autostart_command", "autostart_is_enabled",
    "autostart_enable", "autostart_disable", "autostart_refresh", "SingleInstance", "update_asset_name",
    "install_dir", "launch_swap",
]

NAME = "windows"
GLOBAL_MOUSE = True            # đọc được trạng thái chuột toàn cục (GetAsyncKeyState)
RIGHT_CLICK_EVENTS = ("<Button-3>",)
CAN_SELF_UPDATE = True         # thay thư mục cài bằng script PowerShell

_u32 = ctypes.windll.user32
_TRANSPARENT_KEY = "#010203"


# ---------------------------------------------------------------- cửa sổ
def init_process() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except Exception:
        pass


def dpi_scale(root) -> float:
    try:
        return _u32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0


class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]


_u32.MonitorFromPoint.argtypes = [_POINT, ctypes.c_ulong]
_u32.MonitorFromPoint.restype = ctypes.c_void_p
_u32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]


def work_area(root=None, pt=None) -> tuple:
    """(left, top, right, bottom) vùng dùng được (trừ taskbar, pixel vật lý) của màn hình chứa điểm pt.
    pt=None: màn hình chính. Điểm nằm ngoài mọi màn hình (vd. màn hình đã rút ra) -> màn hình gần nhất."""
    try:
        x, y = pt if pt is not None else (0, 0)
        hmon = _u32.MonitorFromPoint(_POINT(int(x), int(y)), 2 if pt is not None else 1)  # NEAREST / PRIMARY
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        if hmon and _u32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcWork
            return r.l, r.t, r.r, r.b
    except Exception:
        pass
    try:
        r = _RECT()
        _u32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA (màn hình chính)
        return r.l, r.t, r.r, r.b
    except Exception:
        return 0, 0, 1920, 1080


def cursor_pos(root=None) -> tuple:
    p = _POINT()
    _u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def mouse_down() -> bool:
    return bool(_u32.GetAsyncKeyState(0x01) & 0x8000)


def transparent_key():
    """Màu key: pixel có màu này trong cửa sổ bóng là trong suốt thật (-transparentcolor)."""
    return _TRANSPARENT_KEY


def make_transparent(toplevel) -> None:
    toplevel.attributes("-transparentcolor", _TRANSPARENT_KEY)
    toplevel.configure(bg=_TRANSPARENT_KEY)


def round_corners(win, border_hex: str) -> bool:
    """Windows 11: bo góc + viền mảnh (DWMWA_WINDOW_CORNER_PREFERENCE / BORDER_COLOR)."""
    try:
        win.update_idletasks()
        hwnd = _u32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        hr = dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
        h = border_hex.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        col = ctypes.c_uint(r | (g << 8) | (b << 16))
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(col), 4)
        return hr == 0
    except Exception:
        return False


# ---------------------------------------------------------------- hệ thống
def state_dir() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "Wisp"


def open_path(target) -> None:
    os.startfile(str(target))


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

    def value(self) -> int:
        return (self.dwHighDateTime << 32) | self.dwLowDateTime


def process_alive(pid: int, proc_start=None) -> bool:
    """True nếu pid còn chạy. proc_start (FILETIME trong sessions/*.json) dùng để loại pid bị tái sử dụng."""
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return False
        if proc_start:
            ct, et, kt, ut = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
            if k32.GetProcessTimes(h, ctypes.byref(ct), ctypes.byref(et), ctypes.byref(kt), ctypes.byref(ut)):
                try:
                    if abs(ct.value() - int(proc_start)) > 100_000_000:  # lệch > 10 giây
                        return False
                except ValueError:
                    pass
        return True
    finally:
        k32.CloseHandle(h)


def read_credentials(claude_dir: str) -> dict:
    """Object claudeAiOauth của Claude Code: Windows lưu ở ~/.claude/.credentials.json."""
    p = Path(claude_dir) / ".credentials.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        raise RuntimeError("Không đọc được .credentials.json (chưa đăng nhập Claude Code?)")
    return d.get("claudeAiOauth") or {}


# ---------------------------------------------------------------- session
def focus_session(sess: dict) -> tuple:
    return _focus.focus_session(sess)


def open_terminal(cwd: str, args: list, title: str, env: dict) -> tuple:
    """Mở cửa sổ terminal mới chạy args trong cwd (Windows Terminal nếu có, không thì console mới)."""
    wt = shutil.which("wt")
    if wt:
        subprocess.Popen([wt, "-w", "new", "--title", title, "-d", cwd] + args, env=env,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED | NEW_PROCESS_GROUP
    else:
        subprocess.Popen(args, cwd=cwd, env=env, creationflags=0x00000010)  # CREATE_NEW_CONSOLE
    return True, "đã mở terminal"


# ---------------------------------------------------------------- khởi động cùng Windows
def autostart_command() -> str:
    return _auto.launch_command()


def autostart_is_enabled() -> bool:
    return _auto.is_enabled()


def autostart_enable() -> None:
    _auto.enable()


def autostart_disable() -> None:
    _auto.disable()


def autostart_refresh() -> None:
    _auto.refresh_if_enabled()


# ---------------------------------------------------------------- cập nhật
def update_asset_name(version: str) -> str:
    return f"wisp-{version.lstrip('vV')}-win-x64.zip"


def install_dir() -> Path:
    return Path(sys.executable).resolve().parent
