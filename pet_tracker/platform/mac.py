"""Cài đặt interface nền tảng cho macOS — giai đoạn 1 ("bản xem").

Có: bóng trong suốt alpha thật, panel, quota (token từ Keychain), danh sách session + context,
focus cơ bản (Claude desktop qua deep link, Terminal.app / iTerm2 theo tty, app khác qua `open`),
tự khởi động (LaunchAgent), chỉ chạy một bản (file lock + socket).
Chưa có: cập nhật một chạm.

QUAN TRỌNG: file này viết và kiểm tra trên Windows (giả lập import), CHƯA chạy trên Mac thật.
Các điểm cần xác minh trên Mac được đánh dấu `TODO(mac)`.
"""
from __future__ import annotations

import functools
import json
import os
import plistlib
import shlex
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

__all__ = [
    "NAME", "GLOBAL_MOUSE", "CAN_SELF_UPDATE", "RIGHT_CLICK_EVENTS", "WHEEL_PX_PER_DELTA",
    "init_process", "dpi_scale", "work_area", "cursor_pos", "mouse_down", "transparent_key",
    "make_transparent", "round_corners", "state_dir", "open_path", "process_alive", "read_credentials",
    "focus_session", "open_terminal", "set_level", "clip_round", "autostart_command", "autostart_is_enabled",
    "autostart_enable", "autostart_disable", "autostart_refresh", "SingleInstance", "update_asset_name",
    "install_dir", "stage_update", "launch_swap", "system_theme", "reduce_motion", "ui_language", "register_font",
]

NAME = "macOS"
GLOBAL_MOUSE = True             # đọc trạng thái nút chuột toàn cục (CGEventSourceButtonState, không cần quyền)
# Tk 8.6 aqua báo chuột phải là Button-2 (Tk 8.7+/9 đổi sang Button-3); Control-click là chuột phải
# của trackpad / chuột một nút.
RIGHT_CLICK_EVENTS = ("<Button-2>", "<Button-3>", "<Control-Button-1>")
# Tk 8.6 aqua: <MouseWheel> delta tính theo dòng (con lăn 1-3, touchpad ~ pixel/10, tối thiểu 1), không phải bội của 120
WHEEL_PX_PER_DELTA = 12
CAN_SELF_UPDATE = True          # mở dmg, script bash thay Wisp.app khi app thoát (launch_swap)

BUNDLE_ID = "sg.vinova.wisp"
LEGACY_BUNDLE_ID = "sg.vinova.pet-tracker"  # tên cũ (Claude PET): LaunchAgent cũ được đổi sang tên mới
# Keychain của Claude Code (đọc từ code của Claude Code 2.1.302): service "Claude Code-credentials", thêm
# "-<8 hex đầu sha256 của thư mục config>" khi đặt CLAUDE_CONFIG_DIR; account cố định "claude-code-user".
KEYCHAIN_SERVICE = "Claude Code-credentials"
KEYCHAIN_ACCOUNT = "claude-code-user"
CORNER_RADIUS = 10.0            # bo góc panel (macOS 11+ dùng 10pt cho cửa sổ thường)
MENU_BAR_PT = 25                # dự phòng khi không đọc được NSScreen.visibleFrame


def _run(args, timeout=5.0, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)


# ---------------------------------------------------------------- giao diện hệ thống
def system_theme() -> str:
    try:
        return "dark" if "Dark" in _run(["defaults", "read", "-g", "AppleInterfaceStyle"]).stdout else "light"
    except Exception:
        return "light"


def reduce_motion() -> bool:
    try:
        return _run(["defaults", "read", "com.apple.universalaccess", "reduceMotion"]).stdout.strip() == "1"
    except Exception:
        return False


def ui_language() -> str:
    try:
        langs = _run(["defaults", "read", "-g", "AppleLanguages"]).stdout
    except Exception:
        return "en"
    # dạng '( "vi-VN", "en-US" )' trải trên nhiều dòng: lấy mục đầu tiên
    items = [x.strip().strip('"') for x in langs.strip().strip("()").split(",")]
    first = next((x for x in items if x), "")
    return "vi" if first.lower().startswith("vi") else "en"


def register_font(path) -> bool:
    """Nạp font cho process (CTFontManagerRegisterFontsForURL, scope process). TODO(mac): kiểm trên Mac thật."""
    try:
        import ctypes
        import ctypes.util
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        ct = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreText"))
        cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                                               ctypes.c_bool]
        ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        raw = os.fsencode(str(path))
        url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
        if not url:
            return False
        ok = ct.CTFontManagerRegisterFontsForURL(url, 1, None)  # kCTFontManagerScopeProcess
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cf.CFRelease(url)
        return bool(ok)
    except Exception:
        return False


# ---------------------------------------------------------------- cửa sổ
def init_process() -> None:
    pass


def dpi_scale(root) -> float:
    # Tk trên macOS tính theo point; Retina do hệ thống lo. TODO(mac): ảnh PhotoImage có thể mờ trên Retina.
    return 1.0


def _screens() -> list:
    """[(frame, visibleFrame)] của từng màn hình, toạ độ Tk (gốc trên-trái màn hình chính, point), màn hình chính
    (có thanh menu) đầu tiên. visibleFrame đã trừ thanh menu và Dock."""
    import ctypes

    class Rect(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]

    send, cls = _objc()
    scr = send(cls("NSScreen"), "screens")
    raw = []
    for i in range(send(scr, "count", res=ctypes.c_ulong)):
        s = send(scr, "objectAtIndex:", i, argt=(ctypes.c_ulong,))
        raw.append((send(s, "frame", res=Rect, stret=True), send(s, "visibleFrame", res=Rect, stret=True)))
    top = raw[0][0].h  # Cocoa: gốc dưới-trái màn hình chính, y hướng lên

    def conv(r):
        return int(r.x), int(top - r.y - r.h), int(r.x + r.w), int(top - r.y)
    return [(conv(f), conv(v)) for f, v in raw]


def work_area(root=None, pt=None) -> tuple:
    """(left, top, right, bottom) vùng dùng được của màn hình chứa pt (gần nhất nếu nằm ngoài), pt None: màn hình
    chính. Lỗi -> màn hình chính trừ MENU_BAR_PT."""
    try:
        scr = _screens()
        if pt is None:
            return scr[0][1]
        x, y = pt
        return min(scr, key=lambda s: max(s[0][0] - x, 0, x - s[0][2]) ** 2 + max(s[0][1] - y, 0, y - s[0][3]) ** 2)[1]
    except Exception:
        pass
    if root is None:
        return 0, MENU_BAR_PT, 1440, 900
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    return 0, MENU_BAR_PT, w, h - 8   # Dock có thể che đáy; người dùng tự kéo bóng lên


def cursor_pos(root=None) -> tuple:
    """Vị trí con trỏ toàn cục. winfo_pointerxy của Tk trả vị trí cũ khi app không active (panel mở mà đang ở
    app khác), nên đọc thẳng từ Quartz."""
    try:
        if _cg is None:
            _init_cg()
        ev = _cg.CGEventCreate(None)
        try:
            pt = _cg.CGEventGetLocation(ev)
        finally:
            _cf.CFRelease(ev)
        return int(pt.x), int(pt.y)
    except Exception:
        return root.winfo_pointerxy() if root is not None else (0, 0)


_cg = _cf = _Pt = None


def _init_cg():
    """Nạp CoreGraphics/CoreFoundation và khai báo kiểu: thiếu argtypes thì ctypes cắt con trỏ còn 32 bit
    (CFRelease(ev) sẽ segfault). Chỉ gán biến toàn cục sau khi cấu hình xong."""
    global _cg, _cf, _Pt
    import ctypes
    import ctypes.util

    class Pt(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]
    cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
    cg.CGEventSourceButtonState.restype = ctypes.c_bool
    cg.CGEventSourceButtonState.argtypes = [ctypes.c_int32, ctypes.c_uint32]
    cg.CGEventCreate.restype = ctypes.c_void_p
    cg.CGEventCreate.argtypes = [ctypes.c_void_p]
    cg.CGEventGetLocation.restype = Pt
    cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    cf.CFRelease.restype = None
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    _Pt, _cf, _cg = Pt, cf, cg


def mouse_down(button: int = 0) -> bool:
    """Nút chuột đang giữ (0 trái, 1 phải; mọi app). Panel/popup đóng khi bấm ra ngoài. Lỗi -> False."""
    try:
        if _cg is None:
            _init_cg()
        return _cg.CGEventSourceButtonState(1, button)  # kCGEventSourceStateCombinedSessionState
    except Exception:
        return False


def transparent_key():
    return None  # alpha thật, không dùng color key


@functools.lru_cache(maxsize=1)
def _objc():
    """(send, getClass): gọi Objective-C runtime qua ctypes, không cần PyObjC. stret=True cho hàm trả struct lớn
    (NSRect): Intel phải gọi objc_msgSend_stret, Apple Silicon dùng objc_msgSend."""
    import ctypes
    import ctypes.util
    import platform
    x86 = platform.machine() == "x86_64"
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.restype = ctypes.c_void_p

    def send(obj, sel, *args, res=ctypes.c_void_p, argt=(), stret=False):
        f = objc.objc_msgSend_stret if stret and x86 else objc.objc_msgSend
        f.restype, f.argtypes = res, [ctypes.c_void_p, ctypes.c_void_p, *argt]
        return f(obj, objc.sel_registerName(sel.encode()), *args)

    return send, lambda name: objc.objc_getClass(name.encode())


def _ns_windows():
    import ctypes
    send, cls = _objc()
    wins = send(send(cls("NSApplication"), "sharedApplication"), "windows")
    for i in range(send(wins, "count", res=ctypes.c_ulong)):
        yield send, send(wins, "objectAtIndex:", i, argt=(ctypes.c_ulong,))


def _raise_transparent_windows(level: int) -> None:
    """Đặt mức nổi của mọi cửa sổ trong suốt (bóng/island) của tiến trình này.

    Tk aqua: sau -transparent, -topmost không còn tác dụng (NSWindow level về 0) nên bóng/island nằm sau cửa sổ
    của app đang dùng. Gọi thẳng NSWindow.setLevel:."""
    import ctypes
    for send, w in _ns_windows():
        if not send(w, "isOpaque", res=ctypes.c_bool):
            send(w, "setLevel:", level, res=None, argt=(ctypes.c_long,))


def make_transparent(toplevel) -> None:
    # Tk aqua: cửa sổ trong suốt + nền systemTransparent.
    toplevel.attributes("-transparent", True)
    toplevel.configure(bg="systemTransparent")
    toplevel.update_idletasks()  # NSWindow chỉ tồn tại sau khi Tk dựng xong
    try:
        _raise_transparent_windows(25)  # trên panel (19) và thanh menu (24): viền lửa của island lấn lên thanh menu
    except Exception:
        pass


def _with_ns_window(win, fn) -> bool:
    """Gọi fn(send, nswindow) với NSWindow của cửa sổ Tk `win` (tìm theo tiêu đề tạm). Lỗi hoặc chưa có NSWindow
    (cửa sổ chưa từng hiện) -> False."""
    import ctypes
    try:
        win.update_idletasks()
        old = win.title()
        win.title(tag := f"wisp-{id(win)}")
        try:
            for send, w in _ns_windows():
                t = send(w, "title")
                if t and ctypes.string_at(send(t, "UTF8String")).decode() == tag:
                    fn(send, w)
                    return True
        finally:
            win.title(old)
    except Exception:
        pass
    return False


def set_level(win, level: int) -> None:
    """Đặt mức nổi NSWindow của cửa sổ Tk `win`. Lỗi thì bỏ qua."""
    import ctypes
    _with_ns_window(win, lambda send, w: send(w, "setLevel:", level, res=None, argt=(ctypes.c_long,)))


def clip_round(win, radius, border_hex=None) -> bool:
    """Cắt cửa sổ theo hình chữ nhật bo góc `radius` (pt) bằng layer của contentView, viền 1px nếu có border_hex,
    bóng đổ theo hình cắt. radius None: bỏ cắt và bóng (bóng mascot vẽ trên nền trong suốt).

    Tk 8.6 aqua không vẽ ảnh lên Canvas nền systemTransparent (tools/mac_probe.py), nên island và bóng tín hiệu
    là Canvas nền đặc trong cửa sổ được cắt thành viên thuốc / đĩa."""
    import ctypes
    import ctypes.util

    def apply(send, w):
        level = send(w, "level", res=ctypes.c_long)
        send(w, "setOpaque:", False, res=None, argt=(ctypes.c_bool,))
        send(w, "setBackgroundColor:", send(_objc()[1]("NSColor"), "clearColor"), res=None, argt=(ctypes.c_void_p,))
        send(w, "setHasShadow:", radius is not None, res=None, argt=(ctypes.c_bool,))
        cv = send(w, "contentView")
        send(cv, "setWantsLayer:", True, res=None, argt=(ctypes.c_bool,))
        layer = send(cv, "layer")
        send(layer, "setCornerRadius:", float(radius or 0), res=None, argt=(ctypes.c_double,))
        send(layer, "setMasksToBounds:", radius is not None, res=None, argt=(ctypes.c_bool,))
        send(layer, "setBorderWidth:", 1.0 if border_hex else 0.0, res=None, argt=(ctypes.c_double,))
        if border_hex:
            h = border_hex.lstrip("#")
            cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
            cg.CGColorCreateGenericRGB.restype = ctypes.c_void_p
            cg.CGColorCreateGenericRGB.argtypes = [ctypes.c_double] * 4
            col = cg.CGColorCreateGenericRGB(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)), 1.0)
            send(layer, "setBorderColor:", col, res=None, argt=(ctypes.c_void_p,))
        send(w, "invalidateShadow", res=None)
        send(w, "setLevel:", level, res=None, argt=(ctypes.c_long,))  # đổi opaque làm mất mức nổi (-topmost)

    return _with_ns_window(win, apply)


def round_corners(win, border_hex: str) -> bool:
    """Bo góc + viền 1px + bóng đổ cho cửa sổ overrideredirect (panel, menu, thông báo). Cửa sổ để trong suốt để
    bóng đổ theo hình bo (cửa sổ đặc thì bóng vẫn hình chữ nhật)."""
    return clip_round(win, CORNER_RADIUS, border_hex)


# ---------------------------------------------------------------- hệ thống
def state_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Wisp"


def open_path(target) -> None:
    subprocess.Popen(["open", str(target)])


_lstart_cache: dict = {}  # pid -> (lúc đọc, chuỗi lstart): không gọi ps cho mỗi session mỗi 3 giây


def _lstart(pid: int) -> str:
    """Giờ bắt đầu của process đúng như Claude Code ghi vào procStart: `ps -o lstart=` với LC_ALL=C TZ=UTC."""
    now = time.time()
    hit = _lstart_cache.get(pid)
    if hit and now - hit[0] < 60:
        return hit[1]
    r = _run(["ps", "-o", "lstart=", "-p", str(pid)], env=dict(os.environ, LC_ALL="C", TZ="UTC"))
    out = r.stdout.strip() if r.returncode == 0 else ""
    _lstart_cache[pid] = (now, out)
    return out


def process_alive(pid: int, proc_start=None) -> bool:
    """pid còn chạy và (nếu có procStart) đúng là process đã ghi file session, không phải pid bị dùng lại."""
    try:
        pid = int(pid)
        os.kill(pid, 0)
    except PermissionError:
        pass
    except (ProcessLookupError, OSError, ValueError):
        _lstart_cache.pop(pid, None)
        return False
    if not isinstance(proc_start, str) or not proc_start.strip():
        return True
    try:
        return _lstart(pid) == proc_start.strip()
    except Exception:
        return True  # không chạy được ps: coi như còn sống như trước


def _keychain(service: str, account=None) -> str:
    args = ["security", "find-generic-password", "-s", service, "-w"] + (["-a", account] if account else [])
    try:
        r = _run(args, timeout=10)
    except Exception:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _keychain_services() -> list:
    import hashlib
    import unicodedata
    d = os.environ.get("CLAUDE_SECURESTORAGE_CONFIG_DIR") or os.environ.get("CLAUDE_CONFIG_DIR")
    out = [KEYCHAIN_SERVICE]
    if d:  # shortcut: băm đúng chuỗi trong biến môi trường; nếu Claude Code chuẩn hoá đường dẫn khác thì rơi về tên gốc
        out.insert(0, f"{KEYCHAIN_SERVICE}-{hashlib.sha256(unicodedata.normalize('NFC', d).encode()).hexdigest()[:8]}")
    return out


def keychain_json(service: str):
    """JSON Claude Code lưu trong Keychain, hoặc None. Secret dài được chia mảnh: account "<acc>#m" giữ {"n": số
    mảnh}, "<acc>#0".."#n-1" là base64 ghép lại. Thử thêm không có account (bản Claude Code cũ)."""
    for raw in (_keychain(service, KEYCHAIN_ACCOUNT), _keychain(service)):
        try:
            return json.loads(raw)
        except ValueError:
            pass
    meta = _keychain(service, KEYCHAIN_ACCOUNT + "#m")
    if not meta:
        return None
    try:
        import base64
        n = int(json.loads(meta)["n"])
        parts = [_keychain(service, f"{KEYCHAIN_ACCOUNT}#{i}") for i in range(n)]
        return json.loads(base64.b64decode("".join(parts)))
    except (ValueError, KeyError, TypeError):
        return None


def read_credentials(claude_dir: str) -> dict:
    """Object claudeAiOauth: macOS lưu trong Keychain (lần đầu hệ thống hỏi quyền), dự phòng file."""
    for svc in _keychain_services():
        d = keychain_json(svc)
        if isinstance(d, dict) and d:
            return d.get("claudeAiOauth") or d
    p = Path(claude_dir) / ".credentials.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("claudeAiOauth") or {}
    except Exception:
        raise RuntimeError("Không đọc được token Claude Code trong Keychain (chưa đăng nhập, hoặc chưa cho phép "
                           "truy cập Keychain)")


# ---------------------------------------------------------------- session
def _ps(pid: int, field: str) -> str:
    r = _run(["ps", "-o", f"{field}=", "-p", str(int(pid))])
    return r.stdout.strip() if r.returncode == 0 else ""


def _ancestor_app(pid: int, limit: int = 12):
    """Đường dẫn .app của process tổ tiên gần nhất (Terminal, iTerm, Code, Cursor...)."""
    cur = int(pid)
    for _ in range(limit):
        comm = _ps(cur, "comm")
        if ".app/" in comm:
            return comm[:comm.index(".app/") + 4]
        ppid = _ps(cur, "ppid")
        if not ppid.isdigit() or int(ppid) <= 1:
            return None
        cur = int(ppid)
    return None


def _osascript(script: str) -> subprocess.CompletedProcess:
    return _run(["osascript", "-e", script], timeout=10)


def open_terminal(cwd: str, args: list, title: str, env: dict) -> tuple:
    """Mở cửa sổ Terminal.app mới chạy args trong cwd (cần quyền Automation cho Terminal)."""
    cmd = "cd " + shlex.quote(cwd) + " && " + " ".join(shlex.quote(a) for a in args)
    quoted = '"' + cmd.replace("\\", "\\\\").replace('"', '\\"') + '"'
    r = _osascript(f'tell application "Terminal"\n  do script {quoted}\n  activate\nend tell')
    if r.returncode != 0:
        return False, f"không mở được Terminal: {r.stderr.strip()[:120]}"
    return True, "đã mở Terminal"


_TERMINAL_SELECT = '''
tell application "Terminal"
  repeat with w in windows
    repeat with t in tabs of w
      if tty of t is "{tty}" then
        set selected of t to true
        set index of w to 1
        activate
        return "ok"
      end if
    end repeat
  end repeat
end tell
return "notfound"
'''

_ITERM_SELECT = '''
tell application "iTerm2"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if tty of s is "{tty}" then
          select w
          select t
          select s
          activate
          return "ok"
        end if
      end repeat
    end repeat
  end repeat
end tell
return "notfound"
'''


def focus_session(sess: dict) -> tuple:
    host = sess.get("host_session_id") or ""
    if sess.get("entrypoint") == "claude-desktop" and host.startswith("local_"):
        # TODO(mac): xác minh Claude desktop trên macOS xử lý deep link này giống Windows.
        open_path(f"claude://code/continue?session={host}")
        return True, "deep link Claude desktop"
    pid = int(sess["pid"])
    tty = _ps(pid, "tty")
    tty = f"/dev/{tty}" if tty and not tty.startswith("/dev/") and tty not in ("??", "-") else tty
    app = _ancestor_app(pid)
    name = Path(app).stem if app else ""
    # Cần quyền Automation (System Settings > Privacy & Security > Automation) cho Terminal / iTerm2.
    if tty and name == "Terminal":
        r = _osascript(_TERMINAL_SELECT.format(tty=tty))
        if "ok" in r.stdout:
            return True, f"Terminal tab {tty}"
    if tty and name.lower().startswith("iterm"):
        r = _osascript(_ITERM_SELECT.format(tty=tty))
        if "ok" in r.stdout:
            return True, f"iTerm2 session {tty}"
    if app:
        subprocess.Popen(["open", "-a", app])
        return True, f"mở {name}"
    return False, "không tìm thấy app chứa session"


# ---------------------------------------------------------------- tự khởi động (LaunchAgent)
def _agent_path(bundle_id: str = BUNDLE_ID) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{bundle_id}.plist"


def _program_args() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    main = Path(__file__).resolve().parents[2] / "main.py"
    return [sys.executable, str(main)]


def autostart_command() -> str:
    return " ".join(shlex.quote(a) for a in _program_args())


def autostart_is_enabled() -> bool:
    return _agent_path().exists()


def autostart_enable() -> None:
    p = _agent_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        plistlib.dump({"Label": BUNDLE_ID, "ProgramArguments": _program_args(), "RunAtLoad": True,
                       "ProcessType": "Interactive"}, f)


def autostart_disable() -> None:
    try:
        _agent_path().unlink()
    except FileNotFoundError:
        pass


def autostart_refresh() -> None:
    legacy = _agent_path(LEGACY_BUNDLE_ID)
    if legacy.exists():
        legacy.unlink()
        autostart_enable()
    p = _agent_path()
    if not p.exists():
        return
    try:
        with open(p, "rb") as f:
            cur = plistlib.load(f)
    except Exception:
        cur = {}
    if cur.get("ProgramArguments") != _program_args():
        autostart_enable()


# ---------------------------------------------------------------- chỉ chạy một bản
class SingleInstance:
    """File lock trong thư mục state; bản chạy sau gửi 'show' qua Unix socket rồi thoát."""

    def __init__(self):
        import fcntl  # chỉ có trên posix

        d = state_dir()
        d.mkdir(parents=True, exist_ok=True)
        self._sock_path = str(d / "instance.sock")
        self._lock = open(d / "instance.lock", "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.already = False
        except OSError:
            self.already = True

    def notify_running(self) -> bool:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
                c.settimeout(2)
                c.connect(self._sock_path)
                c.sendall(b"show")
            return True
        except OSError:
            return False

    def listen(self, on_show) -> None:
        if self.already:
            return
        try:
            os.unlink(self._sock_path)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(self._sock_path)
        srv.listen(2)

        def loop():
            while True:
                try:
                    conn, _ = srv.accept()
                    with conn:
                        if conn.recv(16).startswith(b"show"):
                            on_show()
                except Exception:
                    continue

        threading.Thread(target=loop, daemon=True, name="single-instance").start()


# ---------------------------------------------------------------- cập nhật
def update_asset_name(version: str) -> str:
    return f"wisp-{version.lstrip('vV')}-macos-universal2.dmg"


def install_dir() -> Path:
    # .../Wisp.app/Contents/MacOS/Wisp -> thư mục chứa .app
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return exe.parent


def stage_update(asset: Path, dest: Path) -> Path:
    """Mở dmg của bản mới (chỉ đọc, không hiện trong Finder), chép .app ra dest. Trả đường dẫn .app mới."""
    mnt = Path(tempfile.mkdtemp(prefix="wisp-dmg-"))
    r = _run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", str(mnt), str(asset)],
             timeout=120)
    if r.returncode != 0:
        shutil.rmtree(mnt, ignore_errors=True)
        raise ValueError(f"không mở được {Path(asset).name}: {r.stderr.strip()[:200]}")
    try:
        apps = [p for p in mnt.iterdir() if p.suffix == ".app" and not p.is_symlink()]
        if len(apps) != 1 or not (apps[0] / "Contents" / "MacOS").is_dir():
            raise ValueError(f"{Path(asset).name} không chứa đúng một .app")
        Path(dest).mkdir(parents=True, exist_ok=True)
        out = Path(dest) / apps[0].name
        r = _run(["ditto", str(apps[0]), str(out)], timeout=300)
        if r.returncode != 0:
            raise ValueError(f"không chép được {apps[0].name}: {r.stderr.strip()[:200]}")
        return out
    finally:
        _run(["hdiutil", "detach", str(mnt), "-force"], timeout=60)
        shutil.rmtree(mnt, ignore_errors=True)


# Đối số: pid đang chạy, .app mới (stage), .app đang cài (target), file log. Lỗi thì trả lại bản cũ và mở nó.
SWAP_SH = r"""
pid="$1"; stage="$2"; target="$3"; log="$4"
L() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$log"; }
L "update: waiting for pid $pid"
for _ in $(seq 1 120); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
sleep 0.5
backup="${target%.app}.old.app"
rm -rf "$backup"
if ! mv "$target" "$backup"; then L "update: FAILED: cannot move $target"; open "$target"; exit 1; fi
L "update: moved $target -> $backup"
if ditto "$stage" "$target"; then
  xattr -dr com.apple.quarantine "$target" 2>/dev/null
  L "update: copied new version into $target"
  open "$target" && L "update: started new version"
  sleep 3
  rm -rf "$backup"
  work="$(dirname "$(dirname "$stage")")"
  case "$(basename "$work")" in pet-update-*) rm -rf "$work" ;; esac
  L "update: done"
else
  L "update: copy failed; restoring backup"
  rm -rf "$target"
  mv "$backup" "$target" && open "$target" && L "update: restarted previous version"
  exit 1
fi
"""


def launch_swap(stage, target_dir, wait_pid, exe_name=None, log_file=None, env=None):
    """Chạy script bash nền (phiên riêng, sống sau khi app thoát) thay target_dir (.app) bằng stage."""
    script = Path(tempfile.gettempdir()) / f"wisp-update-{os.getpid()}.sh"
    script.write_text(SWAP_SH, encoding="utf-8")
    if log_file is None:
        log_file = state_dir() / "update.log"
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(["/bin/bash", str(script), str(int(wait_pid)), str(stage), str(target_dir), str(log_file)],
                            env=env, cwd=tempfile.gettempdir(), start_new_session=True, close_fds=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
