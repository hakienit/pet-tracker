"""Tìm và focus cửa sổ đang host một Claude Code session (Windows).

Khảo sát 2026-10-15 (Claude Code 2.1.300, Claude desktop 2.37337, Windows Terminal 1.24):

1. Claude desktop app: sessions/<pid>.json có hostSessionId = "local_…". App đăng ký scheme
   claude:// và xử lý `claude://code/continue?session=<local_id>` (regex trong app:
   /^local_[A-Za-z0-9-]{1,64}$/) -> mở đúng session trong tab Code. Process claude.exe của session
   là con trực tiếp của Claude.exe nên cũng focus được cửa sổ app qua parent chain.

2. CLI trong Windows Terminal: claude.exe <- cmd/pwsh <- explorer. WindowsTerminal.exe KHÔNG nằm
   trong parent chain (được COM kích hoạt). Nhưng AttachConsole(pid) + GetConsoleWindow() trả về
   cửa sổ ẩn lớp "PseudoConsoleWindow" mà WT đặt owner = cửa sổ WT thật
   (CASCADIA_HOSTING_WINDOW_CLASS). GetAncestor(GA_ROOTOWNER) -> cửa sổ WT. Chỉ focus được cửa sổ,
   không chuyển được tab (WT không có API); Claude Code đặt tiêu đề tab = "✳ <tên session>" nên
   dùng tiêu đề để nhận biết tab đang active.

3. Console cổ điển (conhost): GetConsoleWindow() trả thẳng cửa sổ console có tiêu đề.

4. VS Code / Cursor / JetBrains terminal tích hợp: pseudo console không có owner; đi ngược
   parent chain (claude.exe <- shell <- Code.exe …) và lấy top-level window hiển thị của ancestor.

5. Fallback: tìm cửa sổ có tiêu đề chứa tên session.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import os
import subprocess
import time

k32 = ctypes.windll.kernel32
u32 = ctypes.windll.user32

GA_ROOTOWNER = 3
GW_OWNER = 4
SW_RESTORE = 9
SW_SHOW = 5
TH32CS_SNAPPROCESS = 0x2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ATTACH_PARENT_PROCESS = 0xFFFFFFFF

_SKIP_EXES = {"explorer.exe", "svchost.exe", "services.exe", "wininit.exe", "winlogon.exe", "sihost.exe", "runtimebroker.exe"}


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", w.DWORD),
        ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_table() -> dict:
    """pid -> (parent_pid, exe_name)"""
    out = {}
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1 or not snap:
        return out
    try:
        pe = _PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        if k32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                out[int(pe.th32ProcessID)] = (int(pe.th32ParentProcessID), pe.szExeFile.lower())
                if not k32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        k32.CloseHandle(snap)
    return out


def ancestors(pid: int, table: dict | None = None, limit: int = 12) -> list:
    """[(pid, exe), ...] từ process cha gần nhất lên trên (không gồm chính pid)."""
    table = table or process_table()
    out, cur, seen = [], pid, {pid}
    while len(out) < limit:
        ent = table.get(cur)
        if not ent:
            break
        ppid, _ = ent
        if ppid in seen or ppid not in table:
            break
        seen.add(ppid)
        out.append((ppid, table[ppid][1]))
        cur = ppid
    return out


def window_info(h) -> dict | None:
    if not h:
        return None
    pid = w.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    c = ctypes.create_unicode_buffer(128)
    u32.GetClassNameW(h, c, 128)
    return {"hwnd": int(h), "pid": int(pid.value), "cls": c.value, "title": b.value,
            "visible": bool(u32.IsWindowVisible(h)), "iconic": bool(u32.IsIconic(h))}


def top_windows() -> list:
    """Mọi top-level window đang hiển thị (visible), kèm pid/title/class."""
    out = []
    proc_t = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)

    def cb(h, _):
        if u32.IsWindowVisible(h):
            info = window_info(h)
            if info:
                out.append(info)
        return True

    u32.EnumWindows(proc_t(cb), 0)
    return out


def exe_of_pid(pid: int) -> str:
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return ""
    try:
        b = ctypes.create_unicode_buffer(1024)
        sz = w.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(sz)):
            return os.path.basename(b.value).lower()
    finally:
        k32.CloseHandle(h)
    return ""


def console_window_of(pid: int) -> dict | None:
    """Cửa sổ terminal host console của process pid (Windows Terminal, conhost).
    Dùng AttachConsole nên tạm thời tách console của chính mình (chạy bằng pythonw thì không có)."""
    had_console = bool(k32.GetConsoleWindow())
    k32.FreeConsole()
    try:
        if not k32.AttachConsole(int(pid)):
            return None
        try:
            k32.SetConsoleCtrlHandler(None, True)  # không nhận Ctrl+C từ console đó
            h = k32.GetConsoleWindow()
            info = window_info(h)
            if not info:
                return None
            if info["cls"] == "PseudoConsoleWindow" or not info["visible"]:
                owner = u32.GetAncestor(h, GA_ROOTOWNER)
                if not owner or owner == h:
                    owner = u32.GetWindow(h, GW_OWNER)
                oi = window_info(owner)
                if oi and oi["visible"] and oi["hwnd"] != info["hwnd"]:
                    oi["method"] = "console-owner"
                    return oi
                return None
            info["method"] = "console"
            return info
        finally:
            k32.FreeConsole()
    finally:
        if had_console:
            k32.AttachConsole(ATTACH_PARENT_PROCESS)


def find_window_for_session(sess: dict) -> dict | None:
    """sess: dict từ ClaudeDataStore.active_sessions (cần pid, name/title, entrypoint)."""
    pid = int(sess["pid"])
    table = process_table()
    anc = ancestors(pid, table)
    wins = top_windows()
    by_pid: dict = {}
    for wi in wins:
        by_pid.setdefault(wi["pid"], []).append(wi)

    # 1. console host (Windows Terminal / conhost) — chính xác nhất cho CLI
    try:
        ci = console_window_of(pid)
    except Exception:
        ci = None
    if ci:
        return ci

    # 2. parent chain: process cha gần nhất có cửa sổ hiển thị (Claude.exe, Code.exe, idea64.exe ...)
    for apid, exe in anc:
        if exe in _SKIP_EXES:
            break
        cands = [x for x in by_pid.get(apid, []) if x["title"]] or by_pid.get(apid, [])
        if cands:
            best = cands[0]
            best = dict(best)
            best["method"] = f"parent:{exe}"
            return best

    # 3. tiêu đề cửa sổ chứa tên session (Claude Code đặt title tab = "✳ <tên>")
    names = [n for n in (sess.get("title"), sess.get("name")) if n and len(n) >= 4]
    for wi in wins:
        for n in names:
            if n.lower() in wi["title"].lower():
                wi = dict(wi)
                wi["method"] = "title"
                return wi
    return None


def bring_to_front(hwnd: int) -> bool:
    hwnd = w.HWND(hwnd)
    if u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, SW_RESTORE)
    fg = u32.GetForegroundWindow()
    if fg == hwnd.value:
        return True
    # AttachThreadInput để vượt khoá SetForegroundWindow khi mình không phải foreground
    cur = k32.GetCurrentThreadId()
    fg_tid = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    tgt_tid = u32.GetWindowThreadProcessId(hwnd, None)
    attached = []
    for tid in {fg_tid, tgt_tid}:
        if tid and tid != cur and u32.AttachThreadInput(cur, tid, True):
            attached.append(tid)
    try:
        # nhấn/thả ALT: Windows coi process vừa có input là được phép đổi foreground
        u32.keybd_event(0x12, 0, 0, 0)
        u32.keybd_event(0x12, 0, 2, 0)
        u32.SetForegroundWindow(hwnd)
        u32.BringWindowToTop(hwnd)
        u32.SetActiveWindow(hwnd)
    finally:
        for tid in attached:
            u32.AttachThreadInput(cur, tid, False)
    time.sleep(0.05)
    return u32.GetForegroundWindow() == hwnd.value


def open_deeplink(url: str) -> bool:
    try:
        os.startfile(url)
        return True
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url], creationflags=0x08000000)
            return True
        except Exception:
            return False


def focus_session(sess: dict) -> tuple:
    """Trả (ok, message). Ưu tiên deep link cho Claude desktop, rồi cửa sổ host."""
    msgs = []
    host = sess.get("host_session_id") or ""
    if sess.get("entrypoint") == "claude-desktop" and host.startswith("local_"):
        if open_deeplink(f"claude://code/continue?session={host}"):
            msgs.append("deep link Claude desktop")
    win = None
    try:
        win = find_window_for_session(sess)
    except Exception as e:  # không để UI chết
        msgs.append(f"lỗi tìm cửa sổ: {type(e).__name__}")
    if win:
        ok = bring_to_front(win["hwnd"])
        title = win["title"] or win["cls"]
        msgs.append(f"{'focus' if ok else 'không focus được'} [{win['method']}] {title[:40]}")
        return (ok or bool(host)), " · ".join(msgs)
    if msgs:
        return True, " · ".join(msgs)
    return False, "không tìm thấy cửa sổ host session (xem README)"
