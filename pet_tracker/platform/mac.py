"""Cài đặt interface nền tảng cho macOS — giai đoạn 1 ("bản xem").

Có: bóng trong suốt alpha thật, panel, quota (token từ Keychain), danh sách session + context,
focus cơ bản (Claude desktop qua deep link, Terminal.app / iTerm2 theo tty, app khác qua `open`),
tự khởi động (LaunchAgent), chỉ chạy một bản (file lock + socket).
Chưa có: cập nhật một chạm.

QUAN TRỌNG: file này viết và kiểm tra trên Windows (giả lập import), CHƯA chạy trên Mac thật.
Các điểm cần xác minh trên Mac được đánh dấu `TODO(mac)`.
"""
from __future__ import annotations

import json
import os
import plistlib
import shlex
import socket
import subprocess
import sys
import threading
from pathlib import Path

__all__ = [
    "NAME", "GLOBAL_MOUSE", "CAN_SELF_UPDATE", "RIGHT_CLICK_EVENTS", "WHEEL_PX_PER_DELTA",
    "init_process", "dpi_scale", "work_area", "cursor_pos", "mouse_down", "transparent_key",
    "make_transparent", "round_corners", "state_dir", "open_path", "process_alive", "read_credentials",
    "focus_session", "open_terminal", "set_level", "autostart_command", "autostart_is_enabled",
    "autostart_enable", "autostart_disable", "autostart_refresh", "SingleInstance", "update_asset_name",
    "install_dir", "launch_swap", "system_theme", "reduce_motion", "ui_language", "register_font",
]

NAME = "macOS"
GLOBAL_MOUSE = True             # đọc trạng thái nút chuột toàn cục (CGEventSourceButtonState, không cần quyền)
# Tk 8.6 aqua báo chuột phải là Button-2 (Tk 8.7+/9 đổi sang Button-3); Control-click là chuột phải
# của trackpad / chuột một nút.
RIGHT_CLICK_EVENTS = ("<Button-2>", "<Button-3>", "<Control-Button-1>")
# Tk 8.6 aqua: <MouseWheel> delta tính theo dòng (con lăn 1-3, touchpad ~ pixel/10, tối thiểu 1), không phải bội của 120
WHEEL_PX_PER_DELTA = 12
CAN_SELF_UPDATE = False         # giai đoạn 1: chỉ mở trang release

BUNDLE_ID = "sg.vinova.wisp"
LEGACY_BUNDLE_ID = "sg.vinova.pet-tracker"  # tên cũ (Claude PET): LaunchAgent cũ được đổi sang tên mới
# TODO(mac): xác minh tên service Keychain mà Claude Code dùng (`security dump-keychain | grep -i claude`).
KEYCHAIN_SERVICES = ("Claude Code-credentials",)
CORNER_RADIUS = 10.0            # bo góc panel (macOS 11+ dùng 10pt cho cửa sổ thường)
MENU_BAR_PT = 25                # TODO(mac): lấy đúng vùng dùng được (NSScreen.visibleFrame) nếu cần PyObjC


def _run(args, timeout=5.0) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


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


def work_area(root=None, pt=None) -> tuple:
    # Tk không liệt kê được từng màn hình trên macOS: luôn dùng màn hình chính (pt bị bỏ qua).
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


def _objc():
    """(send, getClass): gọi Objective-C runtime qua ctypes, không cần PyObjC."""
    import ctypes
    import ctypes.util
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.restype = ctypes.c_void_p

    def send(obj, sel, *args, res=ctypes.c_void_p, argt=()):
        f = objc.objc_msgSend
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


def set_level(win, level: int) -> None:
    """Đặt mức nổi NSWindow của cửa sổ Tk `win` (tìm theo tiêu đề tạm). Lỗi thì bỏ qua."""
    import ctypes
    try:
        old = win.title()
        win.title(tag := f"wisp-lvl-{id(win)}")
        for send, w in _ns_windows():
            t = send(w, "title")
            if t and ctypes.string_at(send(t, "UTF8String")).decode() == tag:
                send(w, "setLevel:", level, res=None, argt=(ctypes.c_long,))
                break
        win.title(old)
    except Exception:
        pass


def round_corners(win, border_hex: str) -> bool:
    """Bo góc + viền 1px + bóng đổ cho cửa sổ overrideredirect: layer của contentView bo và cắt nội dung,
    cửa sổ để trong suốt để bóng đổ theo hình bo (cửa sổ đặc thì bóng vẫn hình chữ nhật)."""
    import ctypes
    import ctypes.util
    try:
        win.update_idletasks()
        old = win.title()
        win.title(tag := f"wisp-{id(win)}")
        h = border_hex.lstrip("#")
        for send, w in _ns_windows():
            t = send(w, "title")
            if not t or ctypes.string_at(send(t, "UTF8String")).decode() != tag:
                continue
            level = send(w, "level", res=ctypes.c_long)
            send(w, "setOpaque:", False, res=None, argt=(ctypes.c_bool,))
            send(w, "setBackgroundColor:", send(_objc()[1]("NSColor"), "clearColor"), res=None,
                 argt=(ctypes.c_void_p,))
            send(w, "setHasShadow:", True, res=None, argt=(ctypes.c_bool,))
            cv = send(w, "contentView")
            send(cv, "setWantsLayer:", True, res=None, argt=(ctypes.c_bool,))
            layer = send(cv, "layer")
            send(layer, "setCornerRadius:", CORNER_RADIUS, res=None, argt=(ctypes.c_double,))
            send(layer, "setMasksToBounds:", True, res=None, argt=(ctypes.c_bool,))
            send(layer, "setBorderWidth:", 1.0, res=None, argt=(ctypes.c_double,))
            cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
            cg.CGColorCreateGenericRGB.restype = ctypes.c_void_p
            cg.CGColorCreateGenericRGB.argtypes = [ctypes.c_double] * 4
            col = cg.CGColorCreateGenericRGB(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)), 1.0)
            send(layer, "setBorderColor:", col, res=None, argt=(ctypes.c_void_p,))
            send(w, "invalidateShadow", res=None)
            send(w, "setLevel:", level, res=None, argt=(ctypes.c_long,))  # đổi opaque làm mất mức nổi (-topmost)
            win.title(old)
            return True
        win.title(old)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------- hệ thống
def state_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Wisp"


def open_path(target) -> None:
    subprocess.Popen(["open", str(target)])


def process_alive(pid: int, proc_start=None) -> bool:
    # TODO(mac): procStart trong sessions/<pid>.json trên macOS có định dạng gì? Chưa so để loại pid tái sử dụng.
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError, ValueError):
        return False


def read_credentials(claude_dir: str) -> dict:
    """Object claudeAiOauth: macOS lưu trong Keychain (lần đầu hệ thống hỏi quyền), dự phòng file."""
    for svc in KEYCHAIN_SERVICES:
        try:
            r = _run(["security", "find-generic-password", "-s", svc, "-w"], timeout=10)
        except Exception:
            continue
        if r.returncode == 0 and r.stdout.strip():
            try:
                d = json.loads(r.stdout.strip())
                return d.get("claudeAiOauth") or d
            except ValueError:
                pass
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


def launch_swap(stage, target_dir, wait_pid, exe_name=None, log_file=None, env=None):
    raise RuntimeError("cập nhật một chạm chưa hỗ trợ macOS")
