"""Giao diện: bóng nổi (bubble) + panel stats. tkinter thuần (stdlib)."""
from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont

import base64

from . import __version__, procenv, render, session_ops, updater
from . import platform as plat
from .claude_data import ClaudeDataStore, account_info, short_model
from .config import STATE_DIR, load_config, load_state, save_state
from .quota import fetch_api_usage, fmt_reset, is_session_window

LOG_FILE = STATE_DIR / "wisp.log"


def log(msg: str) -> None:
    """Ghi log nhẹ vào %APPDATA%/Wisp/wisp.log (tự cắt khi > 1MB)."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 1_000_000:
            LOG_FILE.write_text("", encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- palette
# Windows: màu key cho -transparentcolor. macOS: None, bóng dùng PNG có alpha thật.
TRANSPARENT = plat.transparent_key() or "#010203"
BG = "#16171c"
SURFACE = "#1f2027"
LINE = "#2a2b34"
BORDER = "#3a3b47"
HOVER_BORDER = "#55566a"
FG = "#eeeef3"
FG2 = "#c6c7d1"
MUTED = "#8d8e9b"
FAINT = "#5f606d"
TRACK = "#2f3039"
GREEN = "#3fb950"
YELLOW = "#e3b341"
RED = "#f0524f"
BLUE = "#5aa7ff"
ACCENT = "#d97757"   # cam Claude
MODEL_COLORS = {"opus": "#b392f0", "fable": "#e8916f", "sonnet": "#5aa7ff", "haiku": "#4cc9b0"}
BUBBLE_PALETTE = {
    "disc_top": "#2d2e38", "disc_bot": "#18191f", "track": "#353641",
    "rim": "#4b4c5a", "rim_hover": ACCENT, "fringe": "#0d0d11", "cutout": "#121317",
    "key": TRANSPARENT,
}

ICON_REFRESH = ""
ICON_CLOSE = ""
ICON_OPEN = ""
ICON_UPDATE = "\ue896"
ICON_STARTUP_OFF = ""
ICON_CHECK = ""
ICON_FOLDER = ""
ICON_MORE = ""
ICON_CLEAR = ""
ICON_EXIT = ""
SHEET_BG = "#1b1c22"
ROW_HOVER = "#272830"
DANGER_BG = "#3a2326"

FALLBACK_ICONS = {
    "ICON_REFRESH": "\u21bb", "ICON_CLOSE": "\u2715", "ICON_OPEN": "\u2197", "ICON_FOLDER": "\u25a4",
    "ICON_EXIT": "\u23fb", "ICON_UPDATE": "\u2b07", "ICON_CHECK": "\u2611", "ICON_STARTUP_OFF": "\u2610",
    "ICON_MORE": "\u22ef", "ICON_CLEAR": "\u232b",
}

ENTRYPOINTS = {"cli": "CLI", "claude-desktop": "Desktop", "sdk-ts": "SDK", "sdk-py": "SDK", "vscode": "VS Code"}
WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


# ---------------------------------------------------------------- helpers
def fmt_k(n: float) -> str:
    n = float(n or 0)
    if n < 1000:
        return f"{int(n)}"
    if n < 1_000_000:
        v = n / 1000
        return f"{v:.0f}k" if v >= 100 else f"{v:.1f}k"
    if n < 1_000_000_000:
        v = n / 1_000_000
        return f"{v:.0f}M" if v >= 100 else (f"{v:.1f}M" if v >= 10 else f"{v:.2f}M".replace(".00M", "M"))
    return f"{n/1_000_000_000:.2f}B".replace(".00B", "B")


def local_total(u) -> int:
    """Tổng token (input + cache ghi + cache đọc + output) của một cửa sổ usage_window."""
    u = u or {}
    return sum(u.get(k, 0) or 0 for k in ("input", "cache_create", "cache_read", "output"))


def fmt_ago(ts) -> str:
    if not ts:
        return ""
    d = time.time() - ts
    if d < 60:
        return "vừa xong"
    if d < 3600:
        return f"{int(d // 60)} phút trước"
    if d < 86400:
        return f"{int(d // 3600)} giờ trước"
    return f"{int(d // 86400)} ngày trước"


def fmt_clock(ts) -> str:
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts)
    if ts - time.time() < 20 * 3600:
        return f"lúc {dt:%H:%M}"
    return f"{WEEKDAYS[dt.weekday()]} {dt:%d/%m %H:%M}"


def fmt_tier(tier) -> str:
    if not tier:
        return ""
    t = tier.replace("default_", "").replace("claude_", "")
    if t.startswith("max_"):
        return "Max " + t[4:]
    return t.replace("_", " ").title()


def level_color(pct: float, warn: float, danger: float) -> str:
    if pct >= danger:
        return RED
    if pct >= warn:
        return YELLOW
    return GREEN


def model_color(model) -> str:
    fam = (model or "").replace("claude-", "").split("-")[0].lower()
    return MODEL_COLORS.get(fam, BLUE)


_ROOT = None  # tk root, cần cho các hàm nền tảng dùng Tk (macOS)


def _work_area(pt=None) -> tuple:
    """(left, top, right, bottom) vùng dùng được của màn hình chứa điểm pt (None: màn hình chính).
    Pixel vật lý trên Windows."""
    return plat.work_area(_ROOT, pt)


def _cursor_pos() -> tuple:
    return plat.cursor_pos(_ROOT)


def _lbutton_down() -> bool:
    """Chuột trái đang nhấn (toàn hệ thống). Nền tảng không đọc được thì luôn False."""
    return plat.mouse_down() if plat.GLOBAL_MOUSE else False


# ---------------------------------------------------------------- collector thread
class Collector(threading.Thread):
    def __init__(self, cfg: dict, out: queue.Queue):
        super().__init__(daemon=True, name="collector")
        self.cfg = cfg
        self.out = out
        self.store = ClaudeDataStore(cfg["claude_dir"])
        self.stop = threading.Event()
        self.kick = threading.Event()
        self.quota_kick = threading.Event()
        self._git_cache: dict = {}   # cwd -> (lúc lấy, git_state); xoá để lấy lại ngay sau khi dọn dẹp
        self._quota = None
        self._account = account_info(cfg["claude_dir"])

    def refresh_now(self):
        self.quota_kick.set()
        self.kick.set()

    def start(self):
        super().start()
        if self.cfg.get("quota_api_enabled", True):
            # thread riêng: gọi API chậm hoặc mất mạng (timeout 15 giây) không làm đứng danh sách session
            threading.Thread(target=self._quota_loop, daemon=True, name="quota").start()

    def _quota_loop(self):
        interval = max(15.0, float(self.cfg["refresh_quota_sec"]))
        fails = 0
        while not self.stop.is_set():
            res = fetch_api_usage(self.cfg["claude_dir"])
            wait = interval
            if res.get("ok"):
                fails = 0
            else:
                fails += 1
                if res.get("status"):  # lỗi HTTP (429, 401, 5xx…): giãn dần, tối đa 15 phút
                    wait = min(900.0, interval * 2 ** min(fails - 1, 4))
                    wait = max(wait, min(3600.0, float(res.get("retry_after") or 0)))
                log(f"quota: {res.get('error')} (lần {fails}, thử lại sau {wait:.0f}s)")
                # mạng chập chờn: giữ số liệu cũ (tối đa 30 phút) kèm ghi chú lỗi thay vì để panel trống
                prev = self._quota or {}
                if prev.get("windows") and time.time() - (prev.get("fetched_at") or 0) < 1800:
                    res = dict(prev, ok=True, stale_error=res.get("error"))
            self._quota = res
            self.kick.set()  # đẩy snapshot mới ngay
            self.quota_kick.wait(wait)
            self.quota_kick.clear()

    def _git_state(self, cwd, now):
        """git_state có cache 30 giây cho mỗi thư mục: mỗi lần là vài lệnh git."""
        hit = self._git_cache.get(cwd)
        if hit is None or now - hit[0] > 30:
            hit = self._git_cache[cwd] = (now, session_ops.git_state(cwd))
        return hit[1]

    def run(self):
        while not self.stop.is_set():
            try:
                self.store.poll_all()
                sessions = self.store.active_sessions(self.cfg["context_windows"])
                now = time.time()
                for s in sessions:
                    s["git"] = self._git_state(s.get("cwd"), now)
                local = {
                    "5h": self.store.usage_window(5 * 3600, now),
                    "7d": self.store.usage_window(7 * 86400, now),
                }
                self.out.put({
                    "ts": now,
                    "sessions": sessions,
                    "quota": self._quota,
                    "local": local,
                    "account": self._account,
                })
            except Exception as e:  # không để thread chết
                log(f"collector error: {type(e).__name__}: {e}")
                self.out.put({"ts": time.time(), "error": f"{type(e).__name__}: {e}"})
            self.kick.wait(float(self.cfg["refresh_sessions_sec"]))
            self.kick.clear()


# ---------------------------------------------------------------- app
class PetApp:
    def __init__(self):
        plat.init_process()
        self.cfg = load_config()
        self.state = load_state()
        self.q: queue.Queue = queue.Queue()
        self._ops_done: queue.Queue = queue.Queue()   # (tên, ok, thông báo, cwd) từ thread thao tác session
        self.snap = None
        self.sig = None

        global _ROOT
        self.root = tk.Tk()
        self.root.withdraw()
        _ROOT = self.root
        self.S = plat.dpi_scale(self.root)
        self._init_fonts()

        self._img_cache: dict = {}
        self._cards: list = []
        self._hot = None
        self._hover_bubble = False
        self._bub_key = None
        self._rounded = False
        self._dwm_done = False
        self._scrollable = False
        self._flash_until = 0.0
        self._flash_msg = ("", FAINT)
        self.footer_lbl = None
        self._hdr_key = None
        self._parts: dict = {}       # tên phần nội dung -> khung chứa nó trong panel
        self._modal = False
        self._sheet = None
        self._want_show = False
        self._update = None          # kết quả kiểm tra bản mới gần nhất
        self._update_dirty = False   # thread nền báo cần vẽ lại
        self._update_busy = None     # "Đang tải 40%" khi đang cập nhật
        self._update_ready = False
        self._update_stage = None
        self._update_kick = threading.Event()

        self._build_bubble()
        self._build_panel()
        self.collector = Collector(self.cfg, self.q)
        self.collector.start()
        self._start_update_checker()
        self._lbtn_prev = False
        self._drag = None
        self._moved = False
        self.root.bind_all("<MouseWheel>", self._on_wheel)
        try:  # Tk 9: touchpad, chuột cuộn mượt và cuộn khi cửa sổ không focus đến qua sự kiện này
            self.root.bind_all("<TouchpadScroll>", self._on_touchpad)
        except tk.TclError:
            pass
        log(f"start dpi_scale={self.S:.2f} bubble_size={self.size} claude_dir={self.cfg['claude_dir']}")
        if self.cfg.get("config_error"):
            log(self.cfg["config_error"])
        self.root.after(200, self._pump)

    def _init_fonts(self):
        fams = set(tkfont.families(self.root))

        def pick(*names, default=None):
            for n in names:
                if n in fams:
                    return n
            return default

        # Windows: Segoe UI Variable; macOS: font hệ thống (SF Pro qua .AppleSystemUIFont / Helvetica Neue)
        text = pick("Segoe UI Variable Text", "Segoe UI", ".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue",
                    default="TkDefaultFont")
        semi = pick("Segoe UI Variable Text Semibold", "Segoe UI Semibold", ".AppleSystemUIFont", "SF Pro Text",
                    "Helvetica Neue", default=text)
        disp = pick("Segoe UI Variable Display Semib", "Segoe UI Variable Display Semibold", "Segoe UI Semibold",
                    ".AppleSystemUIFont", "SF Pro Display", "Helvetica Neue", default=semi)
        icons = pick("Segoe Fluent Icons", "Segoe MDL2 Assets")
        if icons is None:  # không có font icon: dùng ký tự Unicode thường
            globals().update(FALLBACK_ICONS)
            icons = text
        bold = "bold" if not semi.lower().endswith(("semibold", "semib")) and "Segoe" not in semi else "normal"
        # macOS tính size theo point, chữ trông nhỏ hơn Windows ở cùng size -> cộng thêm
        bump = 3 if plat.IS_MAC else 0
        F = tkfont.Font
        self.f_xs = F(family=text, size=8 + bump)
        self.f_xsb = F(family=semi, size=8 + bump, weight=bold)
        self.f_sm = F(family=text, size=9 + bump)
        self.f_smb = F(family=semi, size=9 + bump, weight=bold)
        self.f_md = F(family=semi, size=10 + bump, weight=bold)
        self.f_title = F(family=disp, size=11 + bump, weight=bold)
        self.f_big = F(family=disp, size=15 + bump, weight=bold)
        self.f_bub = F(family=disp, size=13 + bump, weight=bold)
        self.f_bub_sm = F(family=text, size=7 + bump)
        self.f_badge = F(family=semi, size=8 + bump, weight=bold)
        self.f_icon = F(family=icons, size=10 + bump)
        self.f_icon_sm = F(family=icons, size=8 + bump)

    # ---------- image cache
    def _photo(self, key, rows_fn):
        img = self._img_cache.get(key)
        if img is None:
            if len(self._img_cache) > 300:
                self._img_cache.clear()
            rows = rows_fn()
            img = tk.PhotoImage(width=len(rows[0]), height=len(rows))
            img.put(render.to_photo_data(rows))
            self._img_cache[key] = img
        return img

    # ---------- bubble
    def _build_bubble(self):
        self.size = int(self.cfg["bubble_size"] * self.S)
        b = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        plat.make_transparent(b)
        self._alpha_bubble = plat.transparent_key() is None  # macOS: PNG alpha thật
        self.canvas = tk.Canvas(b, width=self.size, height=self.size,
                                bg="systemTransparent" if self._alpha_bubble else TRANSPARENT,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self._bub_img = tk.PhotoImage(width=self.size, height=self.size)
        self._bub_item = self.canvas.create_image(0, 0, anchor="nw", image=self._bub_img)
        self.bubble = b
        if "x" in self.state and "y" in self.state:
            x, y = self._clamp_bubble(int(self.state["x"]), int(self.state["y"]))
        else:  # lần đầu: góc dưới-phải màn hình chính
            l, t, r, btm = _work_area()
            x, y = r - self.size - int(24 * self.S), btm - self.size - int(24 * self.S)
        b.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        for ev in plat.RIGHT_CLICK_EVENTS:
            self.canvas.bind(ev, self._context_menu)
        self.canvas.bind("<Enter>", lambda e: self._set_bubble_hover(True))
        self.canvas.bind("<Leave>", lambda e: self._set_bubble_hover(False))
        self._draw_bubble()

    def _clamp_bubble(self, x: int, y: int) -> tuple:
        """Giữ bóng trong vùng dùng được của màn hình chứa tâm bóng (màn hình gần nhất nếu nằm ngoài)."""
        s = self.size
        l, t, r, b = _work_area((x + s // 2, y + s // 2))
        return max(l, min(x, r - s)), max(t, min(y, b - s))

    def _bubble_center(self) -> tuple:
        return self.bubble.winfo_x() + self.size // 2, self.bubble.winfo_y() + self.size // 2

    def _set_bubble_hover(self, v: bool):
        if self._hover_bubble != v:
            self._hover_bubble = v
            self._draw_bubble()

    def collector_refresh(self):
        self.collector.refresh_now()
        self._flash("Đang làm mới…", MUTED, 2)

    def _open_claude_dir(self):
        try:
            plat.open_path(self.cfg["claude_dir"])
        except Exception:
            pass

    def _context_menu(self, ev):
        self._bubble_menu(ev.x_root, ev.y_root)

    def _drag_start(self, ev):
        self._drag = (ev.x_root, ev.y_root, self.bubble.winfo_x(), self.bubble.winfo_y())
        self._moved = False

    def _drag_move(self, ev):
        if self._drag is None:
            return
        x0, y0, wx, wy = self._drag
        dx, dy = ev.x_root - x0, ev.y_root - y0
        if abs(dx) > 3 or abs(dy) > 3:
            self._moved = True
        if self._moved:
            self.bubble.geometry(f"+{wx+dx}+{wy+dy}")
            if self.panel_visible:
                self._place_panel()

    def _drag_end(self, ev):
        if self._drag is None:  # nhả chuột sau Control-click (chuột phải trên macOS)
            return
        moved, self._drag, self._moved = self._moved, None, False
        if moved:
            x, y = self._clamp_bubble(self.bubble.winfo_x(), self.bubble.winfo_y())
            self.bubble.geometry(f"+{x}+{y}")
            self.state["x"], self.state["y"] = x, y
            save_state(self.state)
            log(f"moved bubble to {x},{y}")
            if self.panel_visible:
                self._place_panel()
        else:
            self.toggle_panel()

    def _draw_bubble(self):
        c = self.canvas
        s, S = self.size, self.S
        snap = self.snap or {}
        warn, danger = self.cfg["warn_percent"], self.cfg["danger_percent"]
        pct = None
        weekly = False
        quota = snap.get("quota") or {}
        if quota.get("ok") and quota.get("windows"):
            # cửa sổ gần chạm giới hạn nhất (5 giờ hoặc 7 ngày); bằng nhau thì ưu tiên 5 giờ (đứng đầu danh sách)
            wins = [w for w in quota["windows"] if w.get("active", True)] or quota["windows"]
            top = max(wins, key=lambda w: float(w["percent"]))
            pct = float(top["percent"])
            weekly = not is_session_window(top)
        prog = level_color(pct, warn, danger) if pct is not None else MUTED
        sessions = snap.get("sessions") or []
        busy = sum(1 for x in sessions if x["status"] == "busy")
        worst = max((x["context_pct"] for x in sessions), default=0.0)
        warn_col = level_color(worst, warn, danger) if worst >= warn else None
        upd = BLUE if (self._update or {}).get("available") else None
        key = (None if pct is None else round(pct, 1), prog, bool(busy), warn_col, self._hover_bubble, upd)
        sub = "7 ngày" if weekly else f"{len(sessions)} agent"
        if key != self._bub_key:
            self._bub_key = key
            if self._alpha_bubble:
                png = render.bubble_png(s, S, pct, prog, ACCENT if busy else None, warn_col,
                                        self._hover_bubble, BUBBLE_PALETTE, update=upd)
                self._bub_img = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"), format="png")
                self.canvas.itemconfigure(self._bub_item, image=self._bub_img)
            else:
                rows = render.bubble_rows(s, S, pct, prog, ACCENT if busy else None, warn_col,
                                          self._hover_bubble, BUBBLE_PALETTE, update=upd)
                self._bub_img.put(render.to_photo_data(rows))
        c.delete("txt")
        cx = cy = s / 2
        n = len(sessions)
        if pct is not None:
            c.create_text(cx, cy - 4 * S, text=f"{pct:.0f}%", fill=FG, font=self.f_bub, tags="txt")
            c.create_text(cx, cy + 11 * S, text=sub, fill=MUTED, font=self.f_bub_sm, tags="txt")
        else:
            c.create_text(cx, cy - 4 * S, text=str(n), fill=FG, font=self.f_bub, tags="txt")
            c.create_text(cx, cy + 11 * S, text="agent", fill=MUTED, font=self.f_bub_sm, tags="txt")
        if busy:
            rb = 8.5 * S
            c.create_text(s - rb - 0.75, rb + 0.75, text=str(busy), fill="#1a1a1a", font=self.f_badge, tags="txt")

    # ---------- panel
    def _build_panel(self):
        p = tk.Toplevel(self.root)
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        p.configure(bg=BG)
        self._pw_default = int(372 * self.S)
        self._pw_min, self._pw_max = int(320 * self.S), int(760 * self.S)
        self._ph_min = int(260 * self.S)
        self.pw = max(self._pw_min, min(self._pw_max, int(self.state.get("panel_w") or self._pw_default)))
        self._user_h = self.state.get("panel_h")  # None = tự động theo nội dung / màn hình
        self._resize = None
        self.body = tk.Frame(p, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.panel = p
        self.panel_visible = False

        # Khung cố định: header / vùng cuộn / footer. Chỉ nội dung bên trong được dựng lại khi
        # dữ liệu đổi, nên vị trí cuộn không bị reset mỗi lần refresh.
        S = self.S
        self._bar_w = int(12 * S)
        self._hdr = tk.Frame(self.body, bg=BG)
        self._hdr.pack(side="top", fill="x")
        self._ftr = tk.Frame(self.body, bg=BG)
        self._ftr.pack(side="bottom", fill="x")
        mid = tk.Frame(self.body, bg=BG)
        mid.pack(side="top", fill="both", expand=True)
        self._sbar = tk.Canvas(mid, width=self._bar_w, bg=BG, highlightthickness=0, bd=0)
        self._sbar.pack(side="right", fill="y")
        self._scv = tk.Canvas(mid, bg=BG, highlightthickness=0, bd=0, yscrollincrement=1)
        self._scv.pack(side="left", fill="both", expand=True)
        self._content = None
        self._content_win = None
        self._content_h = 1
        self._thumb = (0, 0)
        self._thumb_drag = None
        self._thumb_hover = False
        self._scroll_target = None
        self._scv.bind("<Configure>", lambda e: self._sync_scroll())
        self._sbar.bind("<Configure>", lambda e: self._update_thumb())
        self._sbar.bind("<ButtonPress-1>", self._sb_press)
        self._sbar.bind("<B1-Motion>", self._sb_motion)
        self._sbar.bind("<ButtonRelease-1>", lambda e: setattr(self, "_thumb_drag", None))
        self._sbar.bind("<Enter>", lambda e: self._set_thumb_hover(True))
        self._sbar.bind("<Leave>", lambda e: self._set_thumb_hover(False))
        self._build_grip()
        p.withdraw()

    def _dwm_round(self, win) -> bool:
        """Bo góc + viền mảnh nếu nền tảng hỗ trợ (Windows 11). Trả False để vẽ viền 1px thủ công."""
        return plat.round_corners(win, BORDER)

    def _apply_dwm(self):
        if self._dwm_done:
            return
        self._dwm_done = True
        self._rounded = self._dwm_round(self.panel)
        if not self._rounded:  # Windows 10: viền 1px thủ công
            self.panel.configure(bg=BORDER)
            self.body.pack_configure(padx=1, pady=1)
        log(f"panel dwm rounded={self._rounded}")

    def _focus_for_dismiss(self, win):
        """Nền tảng không đọc được chuột toàn cục (macOS): đóng panel/popup khi app mất focus."""
        try:
            win.focus_force()
        except Exception:
            pass
        if getattr(win, "_dismiss_bound", False):
            return
        win._dismiss_bound = True

        def check():
            try:
                focused = self.root.focus_get()
            except Exception:
                focused = None
            if focused is not None or self._modal or self._resize:
                return
            if self._sheet is not None:
                self._close_sheet()
            elif self.panel_visible:
                log("focus lost -> hide")
                self.hide_panel()

        win.bind("<FocusOut>", lambda e: self.root.after(150, check), add="+")

    def toggle_panel(self):
        if self.panel_visible:
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self):
        self._render_panel(force=True)
        self.panel.attributes("-alpha", 0.0)
        self._place_panel()
        self.panel.deiconify()
        self._apply_dwm()
        self.panel.attributes("-topmost", True)
        self.panel.lift()
        self.panel_visible = True
        self._place_panel()  # lần 2 sau khi map, kích thước thật đã có
        self._fade(1)
        if not plat.GLOBAL_MOUSE:
            self._focus_for_dismiss(self.panel)
        log(f"panel shown at {self.panel.winfo_x()},{self.panel.winfo_y()} size {self.panel.winfo_width()}x{self.panel.winfo_height()}")
        self._lbtn_prev = _lbutton_down()

    def _fade(self, step: int):
        if not self.panel_visible:
            return
        a = min(1.0, step * 0.2)
        try:
            self.panel.attributes("-alpha", a)
        except Exception:
            return
        if a < 1.0:
            self.root.after(14, lambda: self._fade(step + 1))

    def hide_panel(self):
        self._close_sheet()
        self.panel.withdraw()
        self.panel_visible = False
        self._set_hot(None)
        log("panel hidden")

    def _layout(self) -> int:
        """Đặt chiều cao vùng cuộn theo màn hình; trả về tổng chiều cao panel."""
        self.body.update_idletasks()
        l, t, r, b = _work_area(self._bubble_center())
        margin = int(12 * self.S)
        max_h = (b - t) - 2 * margin - (0 if self._rounded else 2)
        if self._user_h:
            max_h = max(self._ph_min, min(max_h, int(self._user_h)))
        hh = self._hdr.winfo_reqheight()
        fh = self._ftr.winfo_reqheight()
        ch = self._content.winfo_reqheight() if self._content else 1
        avail = max(int(140 * self.S), max_h - hh - fh)
        view = min(ch, avail)
        cw = self.pw - self._bar_w - (0 if self._rounded else 2)
        self._scv.configure(height=view, width=cw)
        self._sync_scroll()
        return hh + view + fh + (0 if self._rounded else 2)

    def _place_panel(self):
        ph = self._layout()
        pw = self.pw
        l, t, r, btm = _work_area(self._bubble_center())
        bx, by = self.bubble.winfo_x(), self.bubble.winfo_y()
        gap = int(10 * self.S)
        margin = int(12 * self.S)
        x = bx - pw - gap  # ưu tiên bên trái bóng; nếu không đủ chỗ thì bên phải
        if x < l + margin:
            x = bx + self.size + gap
        if x + pw > r - margin:
            x = max(l + margin, r - margin - pw)
        y = by + self.size - ph  # đáy panel ngang đáy bóng
        y = max(t + margin, min(y, btm - margin - ph))
        self.panel.geometry(f"{pw}x{ph}+{x}+{y}")

    # ---------- scroll
    def _view_h(self) -> int:
        h = self._scv.winfo_height()
        return h if h > 1 else max(1, self._scv.winfo_reqheight())

    def _offset(self) -> float:
        return float(self._scv.canvasy(0))

    def _sync_scroll(self):
        """Cập nhật vùng cuộn theo kích thước thật của canvas (gọi cả khi đang kéo resize)."""
        if not self._content:
            return
        cw = self._scv.winfo_width()
        cw = cw if cw > 1 else max(1, self._scv.winfo_reqwidth())
        self._scv.itemconfigure(self._content_win, width=cw)
        ch = max(1, self._content.winfo_reqheight())
        self._content_h = ch
        vh = self._view_h()
        self._scrollable = ch > vh + 1
        self._scv.configure(scrollregion=(0, 0, cw, max(ch, vh)))
        self._scroll_to(self._offset(), animate=False)

    def _max_offset(self) -> float:
        return max(0.0, self._content_h - self._view_h())

    def _scroll_to(self, off: float, animate: bool = False):
        off = max(0.0, min(self._max_offset(), off))
        if animate:
            self._scroll_target = off
            self._animate_scroll()
            return
        self._scroll_target = None
        total = max(self._content_h, self._view_h())
        self._scv.yview_moveto(off / total if total else 0)
        self._update_thumb()

    def _animate_scroll(self):
        if self._scroll_target is None:
            return
        cur = self._offset()
        d = self._scroll_target - cur
        if abs(d) < 1.5:
            self._scroll_to(self._scroll_target)
            return
        total = max(self._content_h, self._view_h())
        self._scv.yview_moveto((cur + d * 0.35) / total)
        self._update_thumb()
        self.root.after(12, self._animate_scroll)

    def _on_wheel(self, ev):
        self._wheel_by(ev.delta)

    def _on_touchpad(self, ev):
        # %D của <TouchpadScroll> gói deltaX ở 16 bit cao, deltaY ở 16 bit thấp (đều có dấu)
        dy = int(ev.delta) & 0xFFFF
        if dy >= 0x8000:
            dy -= 0x10000
        self._wheel_by(dy)

    def _wheel_by(self, delta: float):
        """delta theo đơn vị Windows: 120 = một nấc con lăn; touchpad gửi nhiều delta nhỏ."""
        if not delta or not self.panel_visible or not self._scrollable or self._sheet:
            return
        x, y = _cursor_pos()
        if not self._inside(self.panel, x, y):
            return
        base = self._scroll_target if self._scroll_target is not None else self._offset()
        self._scroll_to(base - (delta / 120.0) * 72 * self.S, animate=True)

    def _set_thumb_hover(self, v: bool):
        self._thumb_hover = v
        self._update_thumb()

    def _update_thumb(self):
        sb = self._sbar
        sb.delete("all")
        self._thumb = (0, 0)
        if not self._scrollable or not self._content:
            return
        vh = self._view_h()
        ch = max(self._content_h, 1)
        pad = int(4 * self.S)
        track = max(1, vh - 2 * pad)
        L = max(int(28 * self.S), int(track * vh / ch))
        L = min(L, track)
        off = self._offset()
        mo = self._max_offset()
        y0 = pad + int((track - L) * (off / mo if mo else 0))
        w = int((5 if (self._thumb_hover or self._thumb_drag) else 4) * self.S)
        col = MUTED if (self._thumb_hover or self._thumb_drag) else FAINT
        img = self._photo(("thumb", w, L, col),
                          lambda: [list(r) for r in zip(*render.capsule_rows(L, w, 1.0, col, col, BG))])
        x0 = (self._bar_w - w) // 2 - int(1 * self.S)
        sb.create_image(x0, y0, anchor="nw", image=img)
        self._thumb = (y0, y0 + L)

    def _sb_press(self, ev):
        if not self._scrollable:
            return
        y0, y1 = self._thumb
        if y0 <= ev.y <= y1:
            self._thumb_drag = (ev.y, self._offset())
        else:  # bấm vào rãnh: nhảy một trang
            page = self._view_h() * 0.9
            self._scroll_to(self._offset() + (page if ev.y > y1 else -page), animate=True)

    def _sb_motion(self, ev):
        if not self._thumb_drag:
            return
        y_start, off0 = self._thumb_drag
        vh = self._view_h()
        pad = int(4 * self.S)
        y0, y1 = self._thumb
        free = max(1, (vh - 2 * pad) - (y1 - y0))
        self._scroll_to(off0 + (ev.y - y_start) * self._max_offset() / free)

    # ---------- widgets
    def _lbl(self, parent, text, font=None, fg=FG, **kw):
        return tk.Label(parent, text=text, font=font or self.f_sm, fg=fg, bg=parent["bg"], anchor="w",
                        bd=0, padx=0, pady=0, **kw)

    def _ellipsis(self, text: str, font: tkfont.Font, max_px: int) -> str:
        if font.measure(text) <= max_px:
            return text
        while text and font.measure(text + "…") > max_px:
            text = text[:-1]
        return text + "…"

    def _bar(self, parent, pct: float, color: str, width: int, height: float = 6):
        h = max(4, int(height * self.S))
        frac = max(0.0, min(100.0, pct)) / 100.0
        bg = parent["bg"]
        img = self._photo(("bar", width, h, round(frac, 3), color, TRACK, bg),
                          lambda: render.capsule_rows(width, h, frac, color, TRACK, bg))
        c = tk.Canvas(parent, width=width, height=h, bg=bg, highlightthickness=0, bd=0)
        c.create_image(0, 0, anchor="nw", image=img)
        c._img = img
        return c

    def _pill(self, parent, text: str, color: str, fg: str = "#15161a", font=None):
        font = font or self.f_xsb
        S = self.S
        h = font.metrics("linespace") + int(2 * S)
        w = font.measure(text) + int(12 * S)
        bg = parent["bg"]
        img = self._photo(("pill", w, h, color, bg), lambda: render.capsule_rows(w, h, 1.0, color, color, bg))
        c = tk.Canvas(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
        c.create_image(0, 0, anchor="nw", image=img)
        c.create_text(w / 2, h / 2, text=text, fill=fg, font=font)
        c._img = img
        return c

    def _icon_btn(self, parent, glyph: str, cmd, hover_fg=FG, fg=MUTED, font=None):
        b = tk.Label(parent, text=glyph, font=font or self.f_icon, fg=fg, bg=parent["bg"], cursor="hand2",
                     padx=int(5 * self.S), pady=int(3 * self.S))
        b.bind("<Enter>", lambda e: b.configure(fg=hover_fg))
        b.bind("<Leave>", lambda e: b.configure(fg=fg))
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def _text_btn(self, parent, text: str, cmd, hover_fg=FG, fg=MUTED):
        b = tk.Label(parent, text=text, font=self.f_xs, fg=fg, bg=parent["bg"], cursor="hand2")
        b.bind("<Enter>", lambda e: b.configure(fg=hover_fg))
        b.bind("<Leave>", lambda e: b.configure(fg=fg))
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def _section_title(self, parent, text, right=None, right_fg=FAINT, top=14):
        S = self.S
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", pady=(int(top * S), int(6 * S)))
        self._lbl(row, text, font=self.f_xsb, fg=MUTED).pack(side="left")
        if right:
            self._lbl(row, right, font=self.f_xs, fg=right_fg).pack(side="right")
        return row

    def _separator(self, parent):
        tk.Frame(parent, bg=LINE, height=1).pack(fill="x")

    # ---------- render
    def _signature(self, snap: dict) -> dict:
        """Khoá dữ liệu của từng phần nội dung: phần nào đổi khoá thì mới dựng lại phần đó."""
        q = snap.get("quota") or {}
        upd = self._update or {}
        now_min = int(time.time() // 60)
        return {
            "notice": self.cfg.get("config_error"),
            "update": (upd.get("version"), upd.get("available"), upd.get("apply_error"), self._update_busy),
            # giờ lấy số liệu chỉ hiện khi đang dùng số liệu cũ: không đổi số thì làm mới không vẽ lại
            "quota": (tuple((w["key"], round(w["percent"], 1), int((w.get("resets_at") or 0) // 60))
                            for w in q.get("windows", [])),
                      q.get("ok"), q.get("error"), q.get("stale_error"),
                      int((q.get("fetched_at") or 0) // 60) if q.get("stale_error") else None),
            "sessions": (tuple((s["session_id"], s["status"], s["model"], s.get("effort"), s["context_tokens"],
                                s["context_limit"], s["cwd"], s.get("git_branch"), s["name"], s.get("entrypoint"),
                                s["subagents"], s["totals"]["messages"],
                                int((now_min * 60 - (s.get("last_activity") or 0)) // 60),
                                session_ops.state_text(s.get("git")))
                               for s in snap.get("sessions", [])),
                         snap.get("error")),
            "local": tuple(fmt_k(local_total(snap.get("local", {}).get(k))) for k in ("5h", "7d")),
        }

    def _render_panel(self, force=False):
        snap = self.snap or {}
        sig = self._signature(snap)
        if not force and sig == self.sig:
            self._update_footer()
            return
        prev = {} if force else (self.sig or {})
        self.sig = sig
        S = self.S
        padx = int(16 * S)
        # nội dung nằm trong canvas rộng (pw - bar_w); lề phải bớt đi bar_w để hai bên cân nhau
        cpad = (padx, max(0, padx - self._bar_w))
        inner_w = self.pw - padx - cpad[1] - self._bar_w - (0 if self._rounded else 2)

        # header/footer chỉ dựng lại khi tài khoản hoặc chiều rộng đổi: dựng lại mỗi lần làm mới gây chớp
        hdr_key = (snap.get("account"), self.pw)
        if force or hdr_key != self._hdr_key:
            self._hdr_key = hdr_key
            for w in self._hdr.winfo_children() + self._ftr.winfo_children():
                w.destroy()
            self._build_header(self._hdr, snap, padx)
            self._build_footer(self._ftr, padx)
        else:
            self._update_footer()

        if force or self._content is None:
            # khung nội dung mới, mỗi phần một khung con cố định; canvas giữ nguyên nên vị trí cuộn được giữ
            old, old_win = self._content, self._content_win
            new = tk.Frame(self._scv, bg=BG)
            self._parts = {}
            for name in sig:
                self._parts[name] = tk.Frame(new, bg=BG)
                self._parts[name].pack(fill="x")
            tk.Frame(new, bg=BG, height=int(12 * S)).pack(fill="x")
            self._content = new
            # đặt đúng chiều rộng ngay: nếu không, nội dung bị layout và vẽ ở chiều rộng tự nhiên trước rồi mới giãn ra
            cw = self._scv.winfo_width()
            cw = cw if cw > 1 else max(1, self._scv.winfo_reqwidth())
            self._content_win = self._scv.create_window(0, 0, anchor="nw", window=new, width=cw)
            if old_win is not None:
                self._scv.delete(old_win)
            if old is not None:
                old.destroy()

        # chỉ dựng lại phần có dữ liệu đổi: dựng lại cả panel (~150 widget) mất vài trăm ms và làm panel chớp
        builders = {
            "notice": lambda p: self._build_config_notice(p, cpad, inner_w),
            "update": lambda p: self._build_update_banner(p, cpad, inner_w),
            "quota": lambda p: self._build_quota(p, snap, cpad, inner_w),
            "sessions": lambda p: self._build_sessions(p, snap, cpad, inner_w),
            "local": lambda p: self._build_local(p, snap, cpad, inner_w),
        }
        for name, holder in self._parts.items():
            if name in prev and prev[name] == sig[name]:
                continue
            if name == "sessions" and name in prev and self._patch_sessions(snap, prev[name], sig[name], inner_w):
                continue
            if name == "sessions":
                self._cards = []
                self._hot = None
            for w in holder.winfo_children():
                w.destroy()
            builders[name](holder)
        tk.Misc.lift(self._grip)

        if self.panel_visible:
            self._place_panel()
        else:
            self._sync_scroll()

    def _patch_sessions(self, snap, old, new, inner_w) -> bool:
        """Chỉ dựng lại card có dữ liệu đổi (session đang chạy đổi số liệu liên tục).
        False nếu danh sách, trạng thái hoặc lỗi đổi: khi đó dựng lại cả phần (tiêu đề đếm số đang chạy)."""
        (old_cards, old_err), (new_cards, new_err) = old, new
        if (old_err != new_err or len(self._cards) != len(new_cards)
                or [k[:2] for k in old_cards] != [k[:2] for k in new_cards]):  # (session_id, status)
            return False
        for i, (ok, nk, s) in enumerate(zip(old_cards, new_cards, snap.get("sessions") or [])):
            if ok == nk:
                continue
            old_card = self._cards[i][0]
            if self._hot and self._hot[0] is old_card:
                self._hot = None
            self._cards[i] = self._build_session_card(self._card_parent, s, i, inner_w, before=old_card)
            old_card.destroy()
        return True

    def _build_header(self, hd, snap, padx):
        S = self.S
        row = tk.Frame(hd, bg=BG)
        row.pack(fill="x", padx=(padx, int(10 * S)), pady=(int(14 * S), int(12 * S)))
        d = int(34 * S)
        logo = self._photo(("logo", d, BG), lambda: render.logo_rows(d, BG))
        lc = tk.Canvas(row, width=d, height=d, bg=BG, highlightthickness=0, bd=0)
        lc.create_image(0, 0, anchor="nw", image=logo)
        lc._img = logo
        lc.pack(side="left", padx=(0, int(10 * S)))
        titles = tk.Frame(row, bg=BG)
        titles.pack(side="left", fill="x", expand=True)
        self._lbl(titles, "Wisp", font=self.f_title).pack(fill="x")
        acct = snap.get("account") or {}
        sub = " · ".join(x for x in (acct.get("email"), fmt_tier(acct.get("tier"))) if x)
        if sub:
            self._lbl(titles, self._ellipsis(sub, self.f_xs, self.pw - int(140 * S)), font=self.f_xs, fg=MUTED).pack(fill="x")
        self._icon_btn(row, ICON_CLOSE, self.hide_panel, hover_fg=FG).pack(side="right")
        self._icon_btn(row, ICON_REFRESH, self.collector_refresh, hover_fg=BLUE).pack(side="right")
        self._separator(hd)

    def _build_config_notice(self, parent, cpad, inner_w):
        err = self.cfg.get("config_error")
        if not err:
            return
        S = self.S
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", padx=cpad, pady=(int(14 * S), 0))
        card = tk.Frame(sec, bg=SURFACE, padx=int(12 * S), pady=int(10 * S))
        card.pack(fill="x")
        self._lbl(card, err, font=self.f_xs, fg=YELLOW, wraplength=inner_w - int(24 * S),
                  justify="left").pack(fill="x")

    def _build_quota(self, parent, snap, padx, inner_w):
        S = self.S
        warn, danger = self.cfg["warn_percent"], self.cfg["danger_percent"]
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", padx=padx)
        q = snap.get("quota")
        ok = bool(q and q.get("ok"))
        src, src_fg = ("Anthropic API" if ok else ("đã tắt" if not self.cfg.get("quota_api_enabled", True) else "")), FAINT
        if ok and q.get("stale_error"):
            when = time.strftime("%H:%M", time.localtime(q.get("fetched_at") or 0))
            src, src_fg = f"{q['stale_error']} · số liệu lúc {when}", YELLOW
        self._section_title(sec, "GIỚI HẠN SỬ DỤNG", src, right_fg=src_fg)
        if not ok:
            err = (q or {}).get("error") if q else ("đang tải…" if self.cfg.get("quota_api_enabled", True) else "quota_api_enabled = false")
            card = tk.Frame(sec, bg=SURFACE, padx=int(12 * S), pady=int(10 * S))
            card.pack(fill="x")
            self._lbl(card, f"Không lấy được quota: {err}", font=self.f_xs, fg=YELLOW,
                      wraplength=inner_w - int(24 * S), justify="left").pack(fill="x")
            return
        wins = q.get("windows") or []
        if not wins:
            self._lbl(sec, "API không trả về giới hạn nào", font=self.f_xs, fg=MUTED).pack(fill="x")
        cp = int(12 * S)
        for i, w in enumerate(wins):
            col = level_color(w["percent"], warn, danger)
            card = tk.Frame(sec, bg=SURFACE, padx=cp, pady=int(10 * S))
            card.pack(fill="x", pady=(0 if i == 0 else int(6 * S), 0))
            r1 = tk.Frame(card, bg=SURFACE)
            r1.pack(fill="x")
            self._lbl(r1, w["label"], font=self.f_smb, fg=FG).pack(side="left", anchor="s")
            self._lbl(r1, f"{w['percent']:.0f}%", font=self.f_big, fg=col).pack(side="right", anchor="s")
            self._bar(card, w["percent"], col, inner_w - 2 * cp, 6).pack(fill="x", pady=(int(6 * S), int(6 * S)))
            r3 = tk.Frame(card, bg=SURFACE)
            r3.pack(fill="x")
            rs = fmt_reset(w.get("resets_at"))
            if rs:
                self._lbl(r3, rs[0].upper() + rs[1:], font=self.f_xs, fg=MUTED).pack(side="left")
                self._lbl(r3, fmt_clock(w.get("resets_at")), font=self.f_xs, fg=FAINT).pack(side="right")

    def _build_sessions(self, parent, snap, padx, inner_w):
        S = self.S
        sessions = snap.get("sessions") or []
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", padx=padx)
        busy = sum(1 for s in sessions if s["status"] == "busy")
        right = f"{busy} đang chạy" if busy else ""
        self._section_title(sec, f"SESSIONS ({len(sessions)})", right, right_fg=ACCENT)
        if snap.get("error"):
            self._lbl(sec, snap["error"], font=self.f_xs, fg=RED, wraplength=inner_w, justify="left").pack(fill="x")
        if not sessions:
            card = tk.Frame(sec, bg=SURFACE, padx=int(12 * S), pady=int(14 * S))
            card.pack(fill="x")
            self._lbl(card, "Không có session Claude Code nào đang chạy.", font=self.f_xs, fg=MUTED).pack()
            return
        self._card_parent = sec
        for i, s in enumerate(sessions):
            self._cards.append(self._build_session_card(sec, s, i, inner_w))

    def _build_session_card(self, sec, s, i, inner_w, before=None):
        """Một card session; trả (card, arrow). `before`: chèn vào chỗ card cũ khi chỉ card này đổi."""
        S = self.S
        warn, danger = self.cfg["warn_percent"], self.cfg["danger_percent"]
        stripe_w = max(2, int(3 * S))
        cp = int(12 * S)
        cw = inner_w - stripe_w - 2 * cp - 2
        is_busy = s["status"] == "busy"
        status_col = ACCENT if is_busy else (GREEN if s["status"] == "idle" else FAINT)
        card = tk.Frame(sec, bg=SURFACE, highlightthickness=1, highlightbackground=SURFACE,
                        highlightcolor=SURFACE)
        card.pack(fill="x", pady=(0 if i == 0 else int(6 * S), 0), before=before)
        tk.Frame(card, bg=status_col, width=stripe_w).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=SURFACE, padx=cp, pady=int(10 * S))
        inner.pack(side="left", fill="both", expand=True)

        # dòng 1: tên + mũi tên + model + effort
        r1 = tk.Frame(inner, bg=SURFACE)
        r1.pack(fill="x")
        more = tk.Label(r1, text=ICON_MORE, font=self.f_icon_sm, fg=MUTED, bg=SURFACE, cursor="hand2")
        more.pack(side="right", padx=(int(6 * S), 0))
        used = more.winfo_reqwidth() + int(6 * S)
        if s.get("effort"):
            ech = self._pill(r1, s["effort"], "#33343e", fg=FG2, font=self.f_xs)
            ech.pack(side="right", padx=(int(4 * S), 0))
            used += int(ech.cget("width")) + int(4 * S)
        model = short_model(s["model"])
        if model != "?":
            pill = self._pill(r1, model, model_color(s["model"]))
            pill.pack(side="right")
            used += int(pill.cget("width"))
        arrow = tk.Label(r1, text=ICON_OPEN, font=self.f_icon_sm, fg=SURFACE, bg=SURFACE)
        arrow.pack(side="right", padx=(0, int(6 * S)))
        name_w = cw - used - int(22 * S)
        self._lbl(r1, self._ellipsis(s["name"], self.f_md, name_w), font=self.f_md).pack(side="left")

        # dòng 2: thư mục + branch
        r2 = tk.Frame(inner, bg=SURFACE)
        r2.pack(fill="x", pady=(int(2 * S), 0))
        cwd = (s.get("cwd") or "?").rstrip("\\/")
        base = os.path.basename(cwd) or cwd
        parent_dir = os.path.dirname(cwd)
        base_txt = self._ellipsis(base, self.f_xsb, int(cw * 0.55))
        self._lbl(r2, base_txt, font=self.f_xsb, fg=FG2).pack(side="left")
        rest = parent_dir
        br = s.get("git_branch")
        if br and br not in ("HEAD", ""):
            rest = (rest + "   ⎇ " + br) if rest else ("⎇ " + br)
        if rest:
            rest_w = cw - self.f_xsb.measure(base_txt) - int(8 * S)
            self._lbl(r2, self._ellipsis(rest, self.f_xs, rest_w), font=self.f_xs, fg=FAINT).pack(
                side="left", padx=(int(6 * S), 0))

        # dòng 3: context
        col = level_color(s["context_pct"], warn, danger)
        r3 = tk.Frame(inner, bg=SURFACE)
        r3.pack(fill="x", pady=(int(10 * S), int(5 * S)))
        self._lbl(r3, "Context", font=self.f_xs, fg=MUTED).pack(side="left")
        if s["has_transcript"]:
            self._lbl(r3, f"{s['context_pct']:.0f}%", font=self.f_xsb, fg=col).pack(side="right")
            self._lbl(r3, f"{fmt_k(s['context_tokens'])} / {fmt_k(s['context_limit'])}", font=self.f_xs,
                      fg=FG2).pack(side="right", padx=(0, int(8 * S)))
        else:
            self._lbl(r3, "chưa có transcript", font=self.f_xs, fg=FAINT).pack(side="right")
        self._bar(inner, s["context_pct"], col, cw, 5).pack(fill="x")

        # dòng 4: trạng thái + số liệu
        r4 = tk.Frame(inner, bg=SURFACE)
        r4.pack(fill="x", pady=(int(8 * S), 0))
        self._lbl(r4, "● " + ("Đang chạy" if is_busy else ("Rảnh" if s["status"] == "idle" else s["status"])),
                  font=self.f_xsb, fg=status_col).pack(side="left")
        bits = [f"{s['totals']['messages']} msg", f"{fmt_k(s['totals']['output'])} out"]
        if s["subagents"]:
            bits.append(f"{s['subagents']} subagent")
        ep = ENTRYPOINTS.get(s.get("entrypoint") or "", s.get("entrypoint") or "")
        if ep:
            bits.append(ep)
        self._lbl(r4, "  ·  ".join(bits), font=self.f_xs, fg=MUTED).pack(side="left", padx=(int(8 * S), 0))
        ago = fmt_ago(s.get("last_activity"))
        if ago:
            self._lbl(r4, ago, font=self.f_xs, fg=FAINT).pack(side="right")

        # trạng thái git của thư mục session: xong (sạch + đã merge/push) thì dọn được
        gtxt, gkind = session_ops.state_text(s.get("git"))
        if gtxt:
            r5 = tk.Frame(inner, bg=SURFACE)
            r5.pack(fill="x", pady=(int(4 * S), 0))
            self._lbl(r5, self._git_label(s["git"], gtxt), font=self.f_xs,
                      fg=GREEN if gkind == "done" else YELLOW).pack(side="left")

        self._bind_click(card, lambda ev, sess=s: self._focus_session(sess))
        menu = lambda ev, sess=s: self._session_menu(sess, ev.x_root, ev.y_root)
        self._bind_events(card, plat.RIGHT_CLICK_EVENTS, menu)
        more.bind("<Button-1>", menu)
        more.bind("<Enter>", lambda ev: more.configure(fg=FG))
        more.bind("<Leave>", lambda ev: more.configure(fg=MUTED))
        return card, arrow

    @staticmethod
    def _git_label(st: dict, text: str) -> str:
        return f"⎇ {'worktree' if st['linked'] else (st['branch'] or 'git')}: {text}"

    def _build_local(self, parent, snap, padx, inner_w):
        loc = snap.get("local") or {}
        if not loc:
            return
        S = self.S
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", padx=padx)
        self._section_title(sec, "TOKEN ĐÃ DÙNG", "ước tính trên máy này")
        card = tk.Frame(sec, bg=SURFACE, pady=int(12 * S))
        card.pack(fill="x")
        card.grid_columnconfigure(0, weight=1, uniform="c")
        card.grid_columnconfigure(2, weight=1, uniform="c")
        tk.Frame(card, bg=LINE, width=1).grid(row=0, column=1, sticky="ns")
        for i, (key, title) in enumerate((("5h", "5 giờ qua"), ("7d", "7 ngày qua"))):
            col = tk.Frame(card, bg=SURFACE)
            col.grid(row=0, column=2 * i, sticky="w", padx=int(14 * S))
            self._lbl(col, title, font=self.f_xs, fg=MUTED).pack(anchor="w")
            v = tk.Frame(col, bg=SURFACE)
            v.pack(anchor="w", pady=(int(2 * S), 0))
            self._lbl(v, fmt_k(local_total(loc.get(key))), font=self.f_big, fg=FG).pack(side="left")
            self._lbl(v, " tokens", font=self.f_xs, fg=MUTED).pack(side="left", anchor="s", pady=(0, int(3 * S)))

    # ---------- resize
    def _build_grip(self):
        """Tay nắm resize ở góc trên-trái (phía xa bóng). Kéo: đổi rộng/cao. Nhấp đúp: về mặc định."""
        S = self.S
        g = int(14 * S)
        c = tk.Canvas(self.body, width=g, height=g, bg=BG, highlightthickness=0, bd=0, cursor="size_nw_se")
        step = max(3, int(4 * S))
        r = max(1, int(1 * S))
        for i in range(3):
            for j in range(3 - i):
                x, y = int(3 * S) + j * step, int(3 * S) + i * step
                c.create_oval(x - r, y - r, x + r, y + r, fill=FAINT, outline="", tags="dot")
        c.place(x=0, y=0)
        tk.Misc.lift(c)  # Canvas.lift() là raise item, cần raise widget
        c.bind("<Enter>", lambda e: c.itemconfigure("dot", fill=FG2))
        c.bind("<Leave>", lambda e: c.itemconfigure("dot", fill=FAINT))
        c.bind("<ButtonPress-1>", self._resize_start)
        c.bind("<B1-Motion>", self._resize_move)
        c.bind("<ButtonRelease-1>", self._resize_end)
        c.bind("<Double-Button-1>", self._resize_reset)
        self._grip = c

    def _resize_start(self, ev):
        p = self.panel
        self._resize = (ev.x_root, ev.y_root, p.winfo_width(), p.winfo_height(),
                        p.winfo_x() + p.winfo_width(), p.winfo_y() + p.winfo_height())
        self._modal = True

    def _resize_move(self, ev):
        if not self._resize:
            return
        x0, y0, w0, h0, right, bottom = self._resize
        l, t, r, b = _work_area((right - 1, bottom - 1))
        w = max(self._pw_min, min(self._pw_max, w0 - (ev.x_root - x0), right - l))
        h = max(self._ph_min, min(h0 - (ev.y_root - y0), bottom - t))
        self.panel.geometry(f"{int(w)}x{int(h)}+{int(right - w)}+{int(bottom - h)}")

    def _resize_end(self, ev):
        if not self._resize:
            return
        self._resize = None
        self._modal = False
        self._lbtn_prev = _lbutton_down()
        self.pw = max(self._pw_min, min(self._pw_max, self.panel.winfo_width()))
        self._user_h = self.panel.winfo_height()
        self.state["panel_w"], self.state["panel_h"] = self.pw, self._user_h
        save_state(self.state)
        log(f"panel resized to {self.pw}x{self._user_h}")
        self._render_panel(force=True)
        self._place_panel()

    def _resize_reset(self, ev=None):
        self._resize = None
        self._modal = False
        self.pw, self._user_h = self._pw_default, None
        self.state.pop("panel_w", None)
        self.state.pop("panel_h", None)
        save_state(self.state)
        log("panel size reset")
        self._render_panel(force=True)
        self._place_panel()

    def _build_footer(self, ft, padx):
        S = self.S
        self._separator(ft)
        row = tk.Frame(ft, bg=BG)
        row.pack(fill="x", padx=padx, pady=(int(8 * S), int(9 * S)))
        self.footer_lbl = self._lbl(row, "", font=self.f_xs, fg=FAINT)
        self.footer_lbl.pack(side="left")
        self._text_btn(row, "Thoát", self.quit, hover_fg=RED, fg=FAINT).pack(side="right")
        self._lbl(row, f"v{__version__}", font=self.f_xs, fg=FAINT).pack(side="right", padx=(0, int(12 * S)))
        self._update_footer()

    def _update_footer(self):
        """Footer được dựng lại mỗi lần panel vẽ lại: thông báo (flash) còn hạn thì viết lại nó."""
        if not self.footer_lbl:
            return
        try:
            if self._flash_until > time.time():
                text, color = self._flash_msg
                self.footer_lbl.configure(text=self._ellipsis(text, self.f_xs, self.pw - int(90 * self.S)), fg=color)
            elif self.snap:
                ts = time.strftime("%H:%M:%S", time.localtime(self.snap.get("ts", 0)))
                self.footer_lbl.configure(text=f"Cập nhật {ts}  ·  bấm session để mở cửa sổ", fg=FAINT)
        except Exception:
            pass

    def _flash(self, text: str, color: str, secs: float = 6.0):
        self._flash_until = time.time() + secs
        self._flash_msg = (text, color)
        self._update_footer()

    def _bind_click(self, widget, fn):
        try:
            widget.configure(cursor="hand2")
        except Exception:
            pass
        widget.bind("<Button-1>", fn)
        for ch in widget.winfo_children():
            self._bind_click(ch, fn)

    def _bind_events(self, widget, events, fn):
        for ev in events:
            widget.bind(ev, fn)
        for ch in widget.winfo_children():
            self._bind_events(ch, events, fn)

    def _set_hot(self, hot):
        if hot is self._hot:
            return
        try:
            if self._hot:
                card, arrow = self._hot
                card.configure(highlightbackground=SURFACE, highlightcolor=SURFACE)
                arrow.configure(fg=SURFACE)
        except Exception:
            pass
        self._hot = hot
        if hot:
            try:
                card, arrow = hot
                card.configure(highlightbackground=HOVER_BORDER, highlightcolor=HOVER_BORDER)
                arrow.configure(fg=FG2)
            except Exception:
                self._hot = None

    def _poll_hover(self):
        x, y = _cursor_pos()
        hot = None
        try:
            w = self.root.winfo_containing(x, y)
        except Exception:
            w = None
        if w is not None:
            path = str(w)
            for card, arrow in self._cards:
                cp = str(card)
                if path == cp or path.startswith(cp + "."):
                    hot = (card, arrow)
                    break
        if hot is None or self._hot is None or hot[0] is not self._hot[0]:
            self._set_hot(hot)

    # ---------- popup
    def _close_sheet(self):
        if self._sheet is not None:
            try:
                self._sheet.destroy()
            except Exception:
                pass
            self._sheet = None
            self._lbtn_prev = _lbutton_down()

    def _sheet_row(self, parent, icon, label, hint, on_click, enabled=True, danger=False, confirm=None):
        S = self.S
        row = tk.Frame(parent, bg=SHEET_BG, cursor="hand2" if enabled else "arrow")
        row.pack(fill="x", padx=int(6 * S))
        fg = (RED if danger else FG) if enabled else FAINT
        ic = tk.Label(row, text=icon, font=self.f_icon, fg=(RED if danger else MUTED) if enabled else FAINT,
                      bg=SHEET_BG, width=2)
        ic.pack(side="left", padx=(int(8 * S), int(8 * S)), pady=int(7 * S))
        lb = tk.Label(row, text=label, font=self.f_sm, fg=fg, bg=SHEET_BG, anchor="w")
        lb.pack(side="left", fill="x", expand=True)
        ht = tk.Label(row, text=hint, font=self.f_xs, fg=FAINT, bg=SHEET_BG)
        ht.pack(side="right", padx=(0, int(10 * S)))
        parts = (row, ic, lb, ht)
        armed = []  # thao tác nguy hiểm: lần bấm đầu chỉ hiện câu xác nhận

        def paint(bg):
            for p in parts:
                p.configure(bg=bg)

        def reset():
            if armed and row.winfo_exists():
                armed.clear()
                lb.configure(text=label, fg=fg)
                ht.configure(text=hint, fg=FAINT)
                paint(SHEET_BG)

        def click(_e=None):
            if confirm and not armed:
                armed.append(1)
                lb.configure(text=confirm, fg=RED)
                ht.configure(text="bấm lần nữa", fg=RED)
                paint(DANGER_BG)
                self.root.after(4000, reset)
                return
            on_click()

        if enabled:
            for p in parts:
                p.bind("<Enter>", lambda e: paint(DANGER_BG if armed else ROW_HOVER))
                p.bind("<Leave>", lambda e: paint(DANGER_BG if armed else SHEET_BG))
                p.bind("<Button-1>", click)
        return row

    def _new_sheet(self):
        self._close_sheet()
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.0)
        top.configure(bg=SHEET_BG)
        body = tk.Frame(top, bg=SHEET_BG)
        body.pack(fill="both", expand=True)
        self._sheet = top
        return top, body

    def _finish_sheet(self, top, body, W, x, y):
        """Đặt popup cạnh con trỏ (giữ trong màn hình), bo góc, fade-in, Esc để đóng."""
        S = self.S
        top.update_idletasks()
        h = body.winfo_reqheight()
        l, t, r, b = _work_area((x, y))
        m = int(8 * S)
        sx = x - W - m if x + W + m > r else x + m
        sx = max(l + m, sx)
        sy = max(t + m, min(y - int(10 * S), b - h - m))
        top.geometry(f"{W}x{h}+{sx}+{sy}")
        if not self._dwm_round(top):
            top.configure(bg=BORDER)
            body.pack_configure(padx=1, pady=1)
            top.geometry(f"{W + 2}x{h + 2}+{sx}+{sy}")
        top.bind("<Escape>", lambda e: self._close_sheet())
        top.focus_force()
        if not plat.GLOBAL_MOUSE:
            self._focus_for_dismiss(top)
        self._lbtn_prev = _lbutton_down()

        def fade(a=0.0):
            if self._sheet is not top:
                return
            a = min(1.0, a + 0.25)
            top.attributes("-alpha", a)
            if a < 1.0:
                self.root.after(12, lambda: fade(a))
        fade()

    def _toggle_autostart(self):
        try:
            if plat.autostart_is_enabled():
                plat.autostart_disable()
                msg = "Đã tắt tự khởi động"
            else:
                plat.autostart_enable()
                msg = "Đã bật tự khởi động"
            log(f"{msg}: {plat.autostart_command()}")
            self._flash(msg, GREEN, 4)
        except Exception as e:
            log(f"autostart toggle failed: {e}")
            self._flash(f"Không đổi được auto-start: {e}", YELLOW)

    # ---------- cập nhật (GitHub Releases)
    def _start_update_checker(self):
        auto = bool(self.cfg.get("update_check", True))
        api = self.cfg.get("update_api_url") or updater.API_LATEST
        hours = max(1.0, float(self.cfg.get("update_interval_hours") or 24))

        def loop():
            # lần đầu chờ vài giây cho app lên xong; nếu tắt auto thì chỉ chạy khi bấm "Kiểm tra cập nhật"
            self._update_kick.wait(8 if auto else None)
            while not self.collector.stop.is_set():
                manual = self._update_kick.is_set()
                self._update_kick.clear()
                try:
                    info = updater.check(api)
                except Exception as e:
                    info = {"ok": False, "available": False, "error": f"{type(e).__name__}: {e}"}
                prev = self._update or {}
                if prev.get("apply_error") and prev.get("version") == info.get("version"):
                    info["apply_error"] = prev["apply_error"]
                info["manual"] = manual
                self._update = info
                self._update_dirty = True
                log(f"update check: ok={info.get('ok')} available={info.get('available')} "
                    f"latest={info.get('tag')} err={info.get('error')}")
                self._update_kick.wait(hours * 3600 if auto else None)

        threading.Thread(target=loop, daemon=True, name="update-check").start()

    def check_update_now(self):
        self._flash("Đang kiểm tra cập nhật…", MUTED, 6)
        self._update_kick.set()

    def _on_update_state(self):
        u = self._update or {}
        self._draw_bubble()
        if self.panel_visible:
            self._render_panel()
        if u.pop("manual", False):
            if u.get("available"):
                self._flash(f"Có bản mới {u.get('version')}", BLUE, 6)
                if not self.panel_visible:
                    self.show_panel()
            elif u.get("ok"):
                self._flash(f"Đang dùng bản mới nhất (v{__version__})", GREEN, 5)
            else:
                self._flash(f"Không kiểm tra được cập nhật: {u.get('error')}", YELLOW, 8)

    def _open_url(self, url):
        try:
            plat.open_path(url)
        except Exception as e:
            log(f"open url failed: {e}")

    def _button(self, parent, text, color, cmd):
        font, S = self.f_xsb, self.S
        h = font.metrics("linespace") + int(8 * S)
        w = font.measure(text) + int(22 * S)
        bg = parent["bg"]
        hov = render.rgb2hex(render.mix(render.hex2rgb(color), (255, 255, 255), 0.18))
        im_n = self._photo(("btn", w, h, color, bg), lambda: render.capsule_rows(w, h, 1.0, color, color, bg))
        im_h = self._photo(("btn", w, h, hov, bg), lambda: render.capsule_rows(w, h, 1.0, hov, hov, bg))
        c = tk.Canvas(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        it = c.create_image(0, 0, anchor="nw", image=im_n)
        c.create_text(w / 2, h / 2, text=text, fill="#10141a", font=font)
        c._imgs = (im_n, im_h)
        c.bind("<Enter>", lambda e: c.itemconfigure(it, image=im_h))
        c.bind("<Leave>", lambda e: c.itemconfigure(it, image=im_n))
        c.bind("<Button-1>", lambda e: cmd())
        return c

    def _build_update_banner(self, parent, cpad, inner_w):
        u = self._update or {}
        if not u.get("available"):
            return
        S = self.S
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", padx=cpad, pady=(int(14 * S), 0))
        card = tk.Frame(sec, bg=SURFACE)
        card.pack(fill="x")
        tk.Frame(card, bg=BLUE, width=max(2, int(3 * S))).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=SURFACE, padx=int(12 * S), pady=int(10 * S))
        inner.pack(side="left", fill="both", expand=True)
        r1 = tk.Frame(inner, bg=SURFACE)
        r1.pack(fill="x")
        self._lbl(r1, f"Có bản mới {u.get('version')}", font=self.f_md, fg=FG).pack(side="left")
        if self._update_busy:
            self._lbl(r1, self._update_busy, font=self.f_xs, fg=MUTED).pack(side="right")
        else:
            label = "Cập nhật" if updater.can_self_update() else "Tải về"
            self._button(r1, label, BLUE, self._apply_update).pack(side="right")
        r2 = tk.Frame(inner, bg=SURFACE)
        r2.pack(fill="x", pady=(int(4 * S), 0))
        self._lbl(r2, f"Đang dùng {__version__}", font=self.f_xs, fg=MUTED).pack(side="left")
        self._text_btn(r2, "Xem thay đổi", lambda: self._open_url(u.get("html_url") or updater.RELEASES_PAGE),
                       hover_fg=FG, fg=BLUE).pack(side="right")
        if u.get("apply_error"):
            self._lbl(inner, u["apply_error"], font=self.f_xs, fg=YELLOW, wraplength=inner_w - int(30 * S),
                      justify="left").pack(fill="x", pady=(int(6 * S), 0))

    def _set_update_busy(self, text):
        if text != self._update_busy:
            self._update_busy = text
            self._update_dirty = True

    def _apply_update(self):
        u = self._update or {}
        if not u.get("available") or self._update_busy:
            return
        if not updater.can_self_update():  # source, hoặc nền tảng chưa hỗ trợ: chỉ mở trang release
            self._open_url(u.get("html_url") or updater.RELEASES_PAGE)
            self._flash("Đã mở trang release để tải bản mới", MUTED, 6)
            return
        u.pop("apply_error", None)
        self._set_update_busy("Đang tải…")
        log(f"update: downloading {u.get('tag')}")

        def work():
            try:
                stage = updater.download_and_stage(
                    u, progress=lambda f: self._set_update_busy(f"Đang tải {int(f * 100)}%"))
            except Exception as e:
                log(f"update: download failed: {e}")
                u["apply_error"] = f"Không cập nhật được: {e}"
                self._update_busy = None
                self._update_dirty = True
                return
            self._update_stage = stage
            self._set_update_busy("Đang cài…")
            self._update_ready = True

        threading.Thread(target=work, daemon=True, name="update-download").start()

    def _finish_update(self):
        u = self._update or {}
        try:
            updater.launch_swap(self._update_stage, updater.install_dir(), os.getpid(), env=procenv.clean_env())
        except Exception as e:
            log(f"update: launch swap failed: {e}")
            u["apply_error"] = f"Không chạy được trình cài: {e}"
            self._update_busy = None
            self._update_dirty = True
            return
        log(f"update: installing {u.get('tag')} into {updater.install_dir()}, quitting")
        self._flash("Đang cài bản mới, Wisp sẽ tự mở lại…", BLUE, 10)
        self.root.after(400, self.quit)

    def _bubble_menu(self, x, y):
        S = self.S
        W = int(230 * S)
        top, body = self._new_sheet()

        def act(fn):
            def run():
                self._close_sheet()
                fn()
            return run

        tk.Frame(body, bg=SHEET_BG, height=int(6 * S)).pack(fill="x")
        self._sheet_row(body, ICON_REFRESH, "Làm mới ngay", "", act(self.collector_refresh))
        self._sheet_row(body, ICON_FOLDER, "Mở thư mục ~/.claude", "", act(self._open_claude_dir))
        u = self._update or {}
        self._sheet_row(body, ICON_UPDATE, "Kiểm tra cập nhật",
                        f"có {u['version']}" if u.get("available") else f"v{__version__}",
                        act(self.check_update_now))
        on = plat.autostart_is_enabled()
        self._sheet_row(body, ICON_CHECK if on else ICON_STARTUP_OFF,
                        "Chạy cùng Windows" if plat.IS_WINDOWS else "Mở khi đăng nhập", "đang bật" if on else "đang tắt",
                        act(self._toggle_autostart))
        tk.Frame(body, bg=LINE, height=1).pack(fill="x", padx=int(14 * S), pady=int(4 * S))
        self._sheet_row(body, ICON_EXIT, "Thoát Wisp", "", act(self.quit), danger=True)
        tk.Frame(body, bg=SHEET_BG, height=int(6 * S)).pack(fill="x")
        self._finish_sheet(top, body, W, x, y)

    def _focus_session(self, sess: dict):
        try:
            ok, msg = plat.focus_session(sess)
        except Exception as e:
            ok, msg = False, f"lỗi: {type(e).__name__}: {e}"
        log(f"focus session {sess.get('name')!r} pid={sess.get('pid')}: ok={ok} {msg}")
        self._flash(("Đã mở: " if ok else "Không mở được: ") + msg, GREEN if ok else YELLOW)
        if ok:
            self.hide_panel()

    def _session_menu(self, sess: dict, x: int, y: int):
        """Popup dọn dẹp một session: mở, đóng, xoá session, xoá worktree đã xong."""
        S = self.S
        W = int(300 * S)
        pad = int(14 * S)
        top, body = self._new_sheet()

        def act(fn):
            def run():
                self._close_sheet()
                fn()
            return run

        tk.Label(body, text=self._ellipsis(sess.get("name") or "?", self.f_md, W - 2 * pad), font=self.f_md,
                 fg=FG, bg=SHEET_BG, anchor="w").pack(fill="x", padx=pad, pady=(int(12 * S), int(2 * S)))
        tk.Label(body, text=self._ellipsis(sess.get("cwd") or "", self.f_xs, W - 2 * pad), font=self.f_xs,
                 fg=MUTED, bg=SHEET_BG, anchor="w").pack(fill="x", padx=pad)
        st = sess.get("git")
        gtxt, gkind = session_ops.state_text(st)
        if gtxt:
            tk.Label(body, text=self._git_label(st, gtxt), font=self.f_xs, fg=GREEN if gkind == "done" else YELLOW,
                     bg=SHEET_BG, anchor="w").pack(fill="x", padx=pad)
        tk.Frame(body, bg=SHEET_BG, height=int(8 * S)).pack(fill="x")
        tk.Frame(body, bg=LINE, height=1).pack(fill="x")
        tk.Frame(body, bg=SHEET_BG, height=int(4 * S)).pack(fill="x")

        # pid của session Claude desktop thuộc app desktop: không tắt từ ngoài
        desktop = sess.get("entrypoint") == "claude-desktop"
        no_close = "đóng trong Claude app" if desktop else ""
        self._sheet_row(body, ICON_OPEN, "Mở cửa sổ session", "", act(lambda: self._focus_session(sess)))
        self._sheet_row(body, ICON_EXIT, "Handoff rồi đóng", no_close or "ghi handoff trước",
                        act(lambda: self._run_op(sess, "handoff")), enabled=not desktop,
                        confirm="Viết handoff rồi đóng?")
        self._sheet_row(body, ICON_EXIT, "Đóng session", no_close or "không handoff",
                        act(lambda: self._run_op(sess, "close")), enabled=not desktop,
                        confirm="Đóng session này?")
        self._sheet_row(body, ICON_CLEAR, "Xoá session", no_close or "đóng + xoá transcript",
                        act(lambda: self._run_op(sess, "delete")), enabled=not desktop, danger=True,
                        confirm="Xoá hẳn? Không resume được")
        if st and st["linked"]:
            why = session_ops.worktree_block_reason(sess, (self.snap or {}).get("sessions") or [])
            self._sheet_row(body, ICON_FOLDER, "Xoá worktree", why or "đóng session + xoá",
                            act(lambda: self._run_op(sess, "worktree")), enabled=why is None and not desktop,
                            danger=True, confirm="Đóng session, xoá worktree?")
        tk.Frame(body, bg=SHEET_BG, height=int(6 * S)).pack(fill="x")
        self._finish_sheet(top, body, W, x, y)

    def _run_op(self, sess: dict, op: str):
        """handoff | close | delete | worktree. Chạy trên thread nền (claude -p, git, chờ process thoát);
        kết quả về qua _ops_done."""
        name = sess.get("name") or "?"
        self._flash(f"{name}: " + ("đang viết handoff…" if op == "handoff" else "đang xử lý…"), MUTED, 300)

        def work():
            try:
                ok, msg = True, ""
                if op == "handoff":  # handoff lỗi thì không đóng, tránh mất ngữ cảnh
                    ok, path = session_ops.write_handoff(sess, STATE_DIR / "handoffs")
                    msg = path
                if ok:
                    ok, msg = session_ops.close_session(sess)
                    if ok and op == "handoff":
                        msg = f"đã đóng, handoff ở {path}"
                if ok and op == "delete":
                    ok, msg = session_ops.delete_transcript(sess, self.cfg["claude_dir"])
                elif ok and op == "worktree":
                    ok, msg = session_ops.remove_worktree(sess)
            except Exception as e:
                ok, msg = False, f"lỗi: {type(e).__name__}: {e}"
            log(f"session op {op} {name!r} pid={sess.get('pid')} cwd={sess.get('cwd')!r}: ok={ok} {msg}")
            self._ops_done.put((name, ok, msg, sess.get("cwd")))

        threading.Thread(target=work, daemon=True, name=f"op-{op}").start()

    # ---------- loop
    def request_show(self):
        """Gọi từ thread single-instance khi người dùng mở Wisp lần nữa."""
        self._want_show = True

    def _pump(self):
        if self._update_dirty:
            self._update_dirty = False
            self._on_update_state()
        if self._update_ready:
            self._update_ready = False
            self._finish_update()
        if self._want_show:
            self._want_show = False
            log("second launch -> show panel")
            if not self.panel_visible:
                self.show_panel()
            self._flash("Wisp đang chạy rồi", ACCENT, 3)
        try:
            while True:
                name, ok, msg, cwd = self._ops_done.get_nowait()
                self._flash(f"{name}: {msg}", GREEN if ok else YELLOW)
                self.collector._git_cache.pop(cwd, None)
                self.collector.refresh_now()
        except queue.Empty:
            pass
        got = False
        try:
            while True:
                self.snap = self.q.get_nowait()
                got = True
        except queue.Empty:
            pass
        if got:
            self._draw_bubble()
            if self.panel_visible:
                self._render_panel()
        if self._sheet is not None:
            down = _lbutton_down()
            if down and not self._lbtn_prev:
                x, y = _cursor_pos()
                if not self._inside(self._sheet, x, y):
                    self._close_sheet()
                    self._lbtn_prev = True
                    self.root.after(60 if self.panel_visible else 300, self._pump)
                    return
            self._lbtn_prev = down
        elif self.panel_visible:
            down = _lbutton_down()
            if down and not self._lbtn_prev and not self._modal:
                x, y = _cursor_pos()
                if not (self._inside(self.panel, x, y) or self._inside(self.bubble, x, y)):
                    log(f"click outside at {x},{y} -> hide")
                    self.hide_panel()
            self._lbtn_prev = down
            if self.panel_visible:
                self._poll_hover()
        self.root.after(60 if self.panel_visible else 300, self._pump)

    @staticmethod
    def _inside(win, x: int, y: int) -> bool:
        try:
            wx, wy = win.winfo_rootx(), win.winfo_rooty()
            return wx <= x <= wx + win.winfo_width() and wy <= y <= wy + win.winfo_height()
        except Exception:
            return False

    def quit(self):
        self.collector.stop.set()
        self.collector.kick.set()
        try:
            self.root.destroy()
        except Exception:
            pass

    def mainloop(self):
        self.root.report_callback_exception = lambda et, ev, tb: log(f"tk error: {et.__name__}: {ev}")
        self.root.mainloop()


def run(instance=None):
    app = PetApp()
    if instance is not None:
        instance.listen(app.request_show)
    try:
        plat.autostart_refresh()
    except Exception as e:
        log(f"autostart refresh failed: {e}")
    app.mainloop()
