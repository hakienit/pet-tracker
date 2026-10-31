"""Control room: cửa sổ Tk giám sát cây Project > Team > Session > Department > Worker (đầu ra của `org.build`).

Chia hai lớp:
  - hàm thuần (không Tk, kiểm bằng unit test): sanitize, fmt_*, flatten, struct_sig, live_sig, clamp_geometry...
  - `ControlRoom`: Toplevel + ttk.Treeview, chạy ở main thread; không I/O, git, subprocess.

Giao diện cho ui/app.py nối dây (không import ui, không vòng import):

    room = ControlRoom(root, theme, state, save_state, focus_session, log=None)
    room.show()          # tạo lười lần đầu, lần sau đưa cửa sổ lên trước
    room.render(snap)    # từ _pump, main thread; snap["org"] = org.build(...), có thể None
    room.close()         # đóng cửa sổ và lưu vị trí/kích thước; gọi cả khi thoát app

    theme: dict màu/font (khoá thiếu thì dùng mặc định): bg surface line fg fg2 muted faint green yellow red accent sel,
           f_xs f_sm f_smb f_title f_big, scale (dpi_scale), top (lề trên khi kẹp vị trí).
    state: dict state.json đang dùng; vị trí lưu ở state["control_room_geometry"] = {w,h,x,y}.
    save_state(state): ghi state ra đĩa (truyền thẳng config.save_state).
    focus_session(session_id): ui tự tra session và focus cửa sổ của nó. Chỉ gọi khi bấm đúp hoặc Enter.
    log(msg): tuỳ chọn, nhận thông báo lỗi ngắn của focus_session (mặc định không làm gì).

AN TOÀN: mọi chuỗi trong org do agent viết nên không tin cậy. Chúng chỉ đi vào Tk qua `text=`, `values=` và
StringVar, sau `sanitize()`. Không dùng eval/call, không ghép chuỗi Tcl, không đưa chuỗi agent vào iid hay tag:
iid sinh từ bộ đếm (map về dòng bằng dict), tag chỉ lấy từ STATE_TAG theo enum state.
"""
from __future__ import annotations

import math
import ntpath
import re
import sys
import time

from .i18n import t

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk
except ImportError:      # Python không có Tk: hàm thuần vẫn dùng/kiểm được
    tk = tkfont = ttk = None

GEOMETRY_KEY = "control_room_geometry"
MAX_TEXT = 200      # trần mặc định của sanitize
MAX_NAME = 120      # tên dòng trong cây
MAX_STATUS = 20     # status của session
MAX_DETAIL = 300    # giá trị trong khung chi tiết
DEFAULT_SIZE = (960, 600)
MIN_SIZE = (640, 380)
MAX_ROWS_PER_SESSION = 2000     # trần số dòng dưới một session (gồm dòng session và dòng "+N more")
MAX_BAR_COUNT = 10 ** 6         # trần số hiển thị trên thanh tổng; số lớn hơn chỉ hiện trần

# state (enum của org) -> khoá i18n của nhãn; tag Treeview là hằng cố định, không bao giờ lấy từ chuỗi agent
STATE_LABEL = {"running": "cr.st.running", "stuck": "cr.st.stuck", "done": "cr.st.done", "failed": "cr.st.failed",
               "killed": "cr.st.killed", "ended": "cr.st.ended"}
STATE_TAG = {s: "st_" + s for s in STATE_LABEL}
_LIVE = ("running", "stuck")


def state_label(st) -> str:
    """Nhãn hiển thị của state worker theo ngôn ngữ đang chọn; state lạ thì rỗng."""
    return t(STATE_LABEL[st]) if st in STATE_LABEL else ""

_SPACE = re.compile("[\t\n\r\x0b\x0c\x85  ]")
_DROP = re.compile("[\x00-\x1f\x7f-\x9f​-‏‪-‮⁠-⁯؜﻿"
                   "￹-￻￾￿\ud800-\udfff\U000e0000-\U000e007f]")


# ---------------------------------------------------------------- làm sạch và định dạng (thuần)
def sanitize(v, limit: int = MAX_TEXT) -> str:
    """Chuỗi an toàn để hiển thị: xuống dòng/tab -> khoảng trắng; bỏ ký tự điều khiển C0/C1, bidi, zero-width, BOM,
    surrogate đơn, ký tự tag; cắt độ dài. Không phải str thì trả rỗng. Không thay đổi `{ } \\ $ [ %` (Tk không bao giờ
    diễn giải chúng vì chuỗi chỉ đi vào text=/values=)."""
    if not isinstance(v, str):
        return ""
    limit = max(1, int(limit))
    s = _DROP.sub("", _SPACE.sub(" ", v[:limit * 8 + 64])).strip()
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def _n(v):
    """float hữu hạn hoặc None (bool không tính; số lớn hơn float không đổi được thì None)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            f = float(v)
        except OverflowError:
            return None
        if math.isfinite(f):
            return f
    return None


def _i(v) -> int:
    n = _n(v)
    return max(0, int(n)) if n is not None else 0


def fmt_elapsed(sec) -> str:
    """12s / 2m05s / 3h02m / 2d05h; không hợp lệ hoặc âm thì rỗng."""
    s = _n(sec)
    if s is None or s < 0:
        return ""
    s = int(s)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    if s < 86400:
        return f"{s // 3600}h{s % 3600 // 60:02d}m"
    return f"{s // 86400}d{s % 86400 // 3600:02d}h"


def fmt_tokens(n) -> str:
    v = _n(n)
    if v is None:
        return ""
    if v < 1000:
        return str(int(v))
    if v < 1_000_000:
        k = v / 1000
        return f"{k:.0f}k" if k >= 100 else f"{k:.1f}k"
    m = v / 1_000_000
    return f"{m:.0f}M" if m >= 100 else f"{m:.1f}M"


def counts_text(agents: int, tasks: int, stuck: int = 0) -> str:
    """'2 agent (1 treo) · 1 task'; không có việc đang sống thì rỗng."""
    parts = []
    if agents:
        parts.append(t("cr.agent_n", n=agents) + (f" ({t('cr.stuck_n', n=stuck)})" if stuck else ""))
    if tasks:
        parts.append(t("cr.task_n", n=tasks))
    return " · ".join(parts)


def _dicts(v) -> list:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def summary_counts(org_out) -> dict:
    """Số cho thanh tổng; đầu vào hỏng cho 0."""
    o = org_out if isinstance(org_out, dict) else {}
    projects = _dicts(o.get("projects"))
    c = o.get("counts") if isinstance(o.get("counts"), dict) else {}
    sub = c.get("subagent") if isinstance(c.get("subagent"), dict) else {}
    task = c.get("bgtask") if isinstance(c.get("bgtask"), dict) else {}
    def bar(v):
        return min(_i(v), MAX_BAR_COUNT)
    return {"projects": len(projects), "teams": sum(len(_dicts(p.get("teams"))) for p in projects),
            "subagents": bar(sub.get("running")), "tasks": bar(task.get("running")), "stuck": bar(sub.get("stuck"))}


# ---------------------------------------------------------------- org -> dòng phẳng (thuần)
def _t(v, limit=MAX_DETAIL):
    return sanitize(v, limit)


def _state(v) -> str:
    return v if isinstance(v, str) and v in STATE_LABEL else ""


def _team_label(top: str, branch: str) -> str:
    base = ntpath.basename(top.rstrip("\\/")) or top or t("cr.unknown")
    return f"{base} · {branch}" if branch else base


def flatten(org_out, now=None) -> list:
    """Duỗi cây org thành danh sách dòng theo thứ tự cha trước con. Mỗi dòng là dict JSON hoá được:
    key (ổn định, duy nhất; chỉ là khoá dict, không phải iid), kind, parent (key|None), name, state (enum|""),
    summary, status, elapsed, ago, tokens, session_id, detail [(nhãn, giá trị)], ag/tk/stuck (đếm việc sống bên dưới).
    Mọi chuỗi đã qua sanitize. Đầu vào hỏng thì bỏ nhánh hỏng, không ném lỗi."""
    now = _n(now)
    now = time.time() if now is None else now
    rows, used, last_n = [], set(), {}

    def add(kind, key, parent, name, **kw):
        k = key
        if k in used:       # tìm `key#n` từ số đã thử lần trước: các `key#m` (m <= n) đã dùng nên không cần quét lại
            n = last_n.get(key, 0)
            while True:
                n += 1
                k = f"{key}#{n}"
                if k not in used:
                    break
            last_n[key] = n
        used.add(k)
        r = {"key": k, "kind": kind, "parent": parent, "name": name, "state": "", "summary": "", "status": "",
             "elapsed": "", "ago": "", "tokens": 0, "session_id": "", "detail": [], "ag": 0, "tk": 0, "stuck": 0}
        r.update(kw)
        rows.append(r)
        return r

    for p in _dicts((org_out if isinstance(org_out, dict) else {}).get("projects")):
        root = _t(p.get("root"))
        pr = add("project", "p:" + root, None, _t(p.get("name"), MAX_NAME) or root or t("cr.unknown"),
                 detail=[(t("cr.f.root"), root)])
        for tm in _dicts(p.get("teams")):
            top, branch = _t(tm.get("top")), _t(tm.get("branch"), 80)
            tr = add("team", pr["key"] + "/t:" + top, pr["key"], _team_label(top, branch),
                     detail=[(t("cr.f.worktree"), top), (t("cr.f.branch"), branch)])
            for s in _dicts(tm.get("sessions")):
                mark = len(rows)
                _session_rows(add, tr, s, now)
                _cap_rows(rows, add, mark)
    # cộng dồn việc đang sống từ con lên cha (con luôn đứng sau cha trong rows)
    byk = {r["key"]: r for r in rows}
    for r in reversed(rows):
        up = byk.get(r["parent"])
        if up is not None:
            for k in ("ag", "tk", "stuck"):
                up[k] += r[k]
    for r in rows:
        if r["kind"] in ("subagent", "bgtask"):
            r["summary"] = state_label(r["state"])
        else:
            r["summary"] = counts_text(r["ag"], r["tk"], r["stuck"])
    return _cap_global(rows)


MAX_ROWS_TOTAL = 5000   # trần toàn cây (đã cộng dồn trước khi cắt, nên cha vẫn đúng số)


def _cap_global(rows):
    """Giữ MAX_ROWS_TOTAL dòng đầu (cha đứng trước con nên phần giữ lại vẫn là cây hợp lệ). Phần dư thành một dòng
    '+N more' gốc, chỉ đọc, mang số việc đang sống của phần bị cắt. ponytail: global cap, paged tree if fan-out grows."""
    if len(rows) <= MAX_ROWS_TOTAL:
        return rows
    keep, dropped = rows[:MAX_ROWS_TOTAL - 1], rows[MAX_ROWS_TOTAL - 1:]
    leaves = [r for r in dropped if r["kind"] in ("subagent", "bgtask")]
    more = {"key": "#more", "kind": "more", "parent": None, "name": t("cr.more", n=len(dropped)), "state": "",
            "summary": "", "status": "", "elapsed": "", "ago": "", "tokens": 0, "session_id": "", "detail": [],
            "ag": sum(r["ag"] for r in leaves), "tk": sum(r["tk"] for r in leaves),
            "stuck": sum(r["stuck"] for r in leaves)}
    more["summary"] = counts_text(more["ag"], more["tk"], more["stuck"])
    return keep + [more]


def _cap_rows(rows, add, mark):
    """Giữ tối đa MAX_ROWS_PER_SESSION dòng của một session (rows[mark:], dòng đầu là session); phần dư bỏ đi và
    thêm một dòng '+N more' chỉ đọc. Cắt theo thứ tự xuất nên cha vẫn đứng trước con. Việc sống bị gộp được cộng
    vào dòng này để cây cha vẫn đúng."""
    own = rows[mark:]
    if len(own) <= MAX_ROWS_PER_SESSION:
        return
    keep, dropped = own[:MAX_ROWS_PER_SESSION - 1], own[MAX_ROWS_PER_SESSION - 1:]
    workers = [r for r in dropped if r["kind"] in ("subagent", "bgtask")]
    del rows[mark + len(keep):]
    add("more", own[0]["key"] + "/w:more", own[0]["key"], _t(t("cr.more", n=len(workers)), MAX_NAME),
        ag=sum(r["ag"] for r in workers), tk=sum(r["tk"] for r in workers), stuck=sum(r["stuck"] for r in workers))


# chi tiết (nhãn, giá trị) của session, subagent, task nền: dùng chung cho cây và tab Board
def _session_vals(s, now):
    started, last = _n(s.get("started_at")), _n(s.get("last_activity"))
    totals = s.get("totals") if isinstance(s.get("totals"), dict) else {}
    tokens = sum(_i(totals.get(k)) for k in ("input", "cache_create", "cache_read", "output"))
    elapsed = fmt_elapsed(now - started) if started else ""
    ago = fmt_elapsed(now - last) if last else ""
    return _t(s.get("status"), MAX_STATUS), elapsed, ago, tokens


def session_detail(s, now) -> list:
    status, elapsed, ago, tokens = _session_vals(s, now)
    git = s.get("git") if isinstance(s.get("git"), dict) else {}
    return [(t("cr.f.session"), _t(s.get("session_id"), 64)), (t("cr.f.status"), status),
            (t("cr.f.model"), _t(s.get("model"), 60)), (t("cr.f.folder"), _t(s.get("cwd"))),
            (t("cr.f.branch"), _t(git.get("branch"), 80)), (t("cr.f.elapsed"), elapsed),
            (t("cr.f.last"), t("cr.ago", ago=ago) if ago else ""), (t("cr.f.tokens"), fmt_tokens(tokens))]


def _subagent_vals(w, now):
    st = _state(w.get("state"))
    started_w, last_w = _n(w.get("started")), _n(w.get("last_activity"))
    if st in _LIVE:
        el = fmt_elapsed(now - started_w) if started_w is not None else ""
    else:
        el = fmt_elapsed(last_w - started_w) if started_w is not None and last_w is not None else ""
    ag = fmt_elapsed(now - last_w) if last_w is not None else ""
    return st, el, ag, _i(w.get("tokens")), _t(w.get("description")), _t(w.get("type"), 80)


def subagent_detail(w, now) -> list:
    st, el, ag, tok, desc, typ = _subagent_vals(w, now)
    return [(t("cr.f.desc"), desc), (t("cr.f.agent_type"), typ), (t("cr.f.dept"), _t(w.get("department"), 80)),
            (t("cr.f.status"), state_label(st)), (t("cr.f.elapsed"), el),
            (t("cr.f.last"), t("cr.ago", ago=ag) if ag else ""), (t("cr.f.tokens"), fmt_tokens(tok)),
            (t("cr.f.depth"), str(_i(w.get("depth"))))]


def _bgtask_vals(w, now):
    st = _state(w.get("state"))
    started_w = _n(w.get("started"))
    return st, fmt_elapsed(now - started_w) if st == "running" and started_w is not None else ""


def bgtask_detail(w, now) -> list:
    st, el = _bgtask_vals(w, now)
    return [(t("cr.f.task_id"), _t(w.get("id"), 80)), (t("cr.f.status"), state_label(st)),
            (t("cr.f.elapsed"), el), (t("cr.f.tool_use"), _t(w.get("tool_use_id"), 80))]


def _session_rows(add, team, s, now):
    sid = s.get("session_id") if isinstance(s.get("session_id"), str) else ""
    status, elapsed, ago, tokens = _session_vals(s, now)
    sr = add("session", team["key"] + "/s:" + sid, team["key"],
             _t(s.get("name"), MAX_NAME) or _t(sid, 8) or t("cr.anon_session"),
             status=status, elapsed=elapsed, ago=ago, tokens=tokens, session_id=sid, detail=session_detail(s, now))
    ws = _dicts(s.get("workers"))
    subs = [w for w in ws if w.get("kind") == "subagent"]
    tasks = [w for w in ws if w.get("kind") == "bgtask"]

    # con của subagent theo id cha; cha không có/không tìm thấy/tự trỏ thì là gốc. Vòng (org không tạo ra) được
    # chặn bằng `seen`: worker nằm trong vòng không có gốc nên được đưa lên làm gốc ở vòng lặp cuối.
    idx = {}
    for i, w in enumerate(subs):
        idx.setdefault(_t(w.get("id"), 80), i)
    kids, roots = {i: [] for i in range(len(subs))}, []
    for j, w in enumerate(subs):
        pid = w.get("parent") if isinstance(w.get("parent"), str) else None
        pi = idx.get(_t(pid, 80)) if pid else None
        (kids[pi] if pi is not None and pi != j else roots).append(j)
    groups, seen = {}, set()

    def emit(j, parent_key):
        stack = [(j, parent_key)]
        while stack:
            j, pk = stack.pop()
            if j in seen:
                continue
            seen.add(j)
            w = subs[j]
            st, el, ag, tok, desc, typ = _subagent_vals(w, now)
            r = add("subagent", sr["key"] + "/w:sub:" + _t(w.get("id"), 80), pk,
                    _t(desc, MAX_NAME) or typ or t("cr.anon_subagent"),
                    state=st, elapsed=el, ago=ag, tokens=tok, ag=int(st in _LIVE), stuck=int(st == "stuck"),
                    detail=subagent_detail(w, now))
            for c in reversed(kids[j]):
                stack.append((c, r["key"]))

    def group_of(j):
        name = _t(subs[j].get("department"), 80) or _t(subs[j].get("type"), 80) or t("cr.other")
        if name not in groups:
            groups[name] = add("dept", sr["key"] + "/d:" + name, sr["key"], name)
        return groups[name]["key"]

    for j in roots:
        emit(j, group_of(j))
    for j in range(len(subs)):
        if j not in seen:
            emit(j, group_of(j))
    if tasks:
        gk = add("dept", sr["key"] + "/d:#tasks", sr["key"], t("cr.bg_group"))["key"]
        for w in tasks:
            st, el = _bgtask_vals(w, now)
            add("bgtask", sr["key"] + "/w:bg:" + _t(w.get("id"), 80), gk, t("cr.bg_task", id=_t(w.get("id"), 24)),
                state=st, elapsed=el, tk=int(st == "running"), detail=bgtask_detail(w, now))


def row_tag(r):
    """Tag cố định cho dòng: theo state của worker; nhóm có worker treo bên dưới thì cảnh báo."""
    if r["state"]:
        return STATE_TAG.get(r["state"])
    return STATE_TAG["stuck"] if r["stuck"] else None


def live_text(r) -> str:
    """Cột 'Hoạt động': thời gian chạy, token, lần hoạt động cuối."""
    if r["kind"] in ("project", "team", "dept"):
        return ""
    parts = [r["status"], r["elapsed"], t("cr.tok", n=fmt_tokens(r["tokens"])) if r["tokens"] else "",
             t("cr.ago", ago=r["ago"]) if r["ago"] else ""]
    return " · ".join(p for p in parts if p)


def struct_sig(rows) -> tuple:
    """Chữ ký hình dạng cây (dòng, tên, state): đổi thì dựng lại cây."""
    return tuple((r["key"], r["kind"], r["parent"], r["name"], r["state"]) for r in rows)


def live_sig(rows) -> tuple:
    """Chữ ký phần đổi liên tục (status, thời gian chạy, hoạt động cuối, token): đổi thì chỉ cập nhật nhãn."""
    return tuple((r["key"], r["status"], r["elapsed"], r["ago"], r["tokens"]) for r in rows)


# ---------------------------------------------------------------- hình học cửa sổ (thuần)
def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def clamp_geometry(saved, screen, default, minimum, top=0) -> tuple:
    """(w, h, x, y) hợp lệ và nằm trong màn hình. `saved` hỏng/thiếu thì dùng `default` căn giữa.
    ponytail: chỉ màn hình chính; cửa sổ lưu ở màn hình phụ sẽ được kéo về màn hình chính."""
    sw, sh = screen
    g = saved if isinstance(saved, dict) else {}
    w, h, x, y = (_int(g.get(k)) for k in ("w", "h", "x", "y"))
    ok = None not in (w, h, x, y)
    if not ok:
        w, h = default
    w = max(min(minimum[0], sw), min(w, sw))
    h = max(min(minimum[1], sh - top), min(h, sh - top))
    if not ok:
        return w, h, (sw - w) // 2, top + (sh - top - h) // 2
    return w, h, max(0, min(x, sw - w)), max(top, min(y, sh - h))


# ---------------------------------------------------------------- cửa sổ
_DEFAULT_THEME = {"bg": "#16171c", "surface": "#1f2027", "line": "#2a2b34", "fg": "#eeeef3", "fg2": "#c6c7d1",
                  "muted": "#8d8e9b", "faint": "#5f606d", "green": "#3fb950", "yellow": "#e3b341", "red": "#f0524f",
                  "accent": "#d97757", "sel": "#2f3039"}


class ControlRoom:
    def __init__(self, root, theme, state, save_state, focus_session, log=None):
        self.root, self.state, self._save, self._focus = root, state, save_state, focus_session
        self._log = log if callable(log) else (lambda msg: None)
        self.th = {**_DEFAULT_THEME, **(theme if isinstance(theme, dict) else {})}
        s = _n(self.th.get("scale"))
        self.S = min(max(s, 0.5), 4.0) if s and s > 0 else 1.0
        self.win = self.tree = None
        self._org = None            # org mới nhất, giữ cả khi cửa sổ đóng để mở lại có ngay
        self._rows: dict = {}       # iid -> dòng
        self._iid_of: dict = {}     # key -> iid
        self._vals: dict = {}       # iid -> values đang hiển thị
        self._counter = 0
        self._rebuilds = 0
        self._struct = self._live = None

    # ---------- vòng đời
    def show(self):
        """Đưa cửa sổ lên trước, hoặc dựng lại nếu chưa có cửa sổ hoặc cây đã mất. Trả True khi cửa sổ đã hiện;
        False khi dựng lỗi (đã reset và ghi log qua _report, không ném ra)."""
        if self.win is not None and self.tree is not None:
            try:
                self.win.deiconify()
                self.win.lift()
                self.win.focus_force()
                return True
            except tk.TclError:
                pass
        if self.win is not None:        # cửa sổ còn sót nhưng cây thiếu: huỷ rồi dựng lại
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self._reset()
        try:
            self._build()
            self._apply(flatten(self._org, None))
            return True
        except Exception as e:
            self._report("show: " + repr(e)[:200])
            return False

    def _report(self, msg):
        try:
            self._log(msg)
        except Exception:
            pass

    def close(self):
        win = self.win
        if win is None:
            return
        try:
            if win.winfo_viewable():
                self.state[GEOMETRY_KEY] = {"w": win.winfo_width(), "h": win.winfo_height(),
                                            "x": win.winfo_x(), "y": win.winfo_y()}
                self._save(self.state)
        except Exception:
            pass
        self._reset()
        try:
            win.destroy()
        except tk.TclError:
            pass

    def _reset(self):
        """Bỏ mọi tham chiếu tới cửa sổ/cây cũ; org (_org) giữ nguyên."""
        self.win = self.tree = None
        self._rows, self._iid_of, self._vals, self._struct, self._live = {}, {}, {}, None, None

    def _on_destroy(self, ev):
        # <Destroy> của toplevel cũng nổi lên từ widget con: chỉ reset khi chính cửa sổ bị huỷ (close() đã reset trước)
        if self.win is not None and ev.widget is self.win:
            self._reset()

    def render(self, snap, now=None):
        """Gọi từ _pump (main thread) với snapshot; chỉ nhận snap["org"]. Trước show() chỉ lưu org."""
        self._org = snap.get("org") if isinstance(snap, dict) else None
        if self.win is not None and self.tree is not None:
            self._apply(flatten(self._org, now))

    # ---------- dựng cửa sổ
    def _font(self, name):
        return self.th.get(name) or "TkDefaultFont"

    def _build(self):
        """Dựng cửa sổ. Lỗi giữa chừng: huỷ Toplevel (bỏ qua lỗi), reset trạng thái rồi ném lại."""
        self._reset()
        try:
            self._build_ui()
        except Exception:
            win = self.win
            if win is not None:
                try:
                    win.destroy()
                except tk.TclError:
                    pass
            self._reset()
            raise

    def _build_ui(self):
        th, S = self.th, self.S
        top = th["top"] if isinstance(th.get("top"), int) else (28 if sys.platform == "darwin" else 0)
        w, h, x, y = clamp_geometry(self.state.get(GEOMETRY_KEY), (self.root.winfo_screenwidth(), self.root.winfo_screenheight()),
                                    (int(DEFAULT_SIZE[0] * S), int(DEFAULT_SIZE[1] * S)),
                                    (int(MIN_SIZE[0] * S), int(MIN_SIZE[1] * S)), int(top * S))
        win = self.win = tk.Toplevel(self.root)
        win.title(t("cr.window"))
        win.configure(bg=th["bg"])
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.minsize(int(MIN_SIZE[0] * S), int(MIN_SIZE[1] * S))
        win.protocol("WM_DELETE_WINDOW", self.close)
        win.bind("<Destroy>", self._on_destroy)
        pad = int(12 * S)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)

        # thanh tổng
        bar = tk.Frame(win, bg=th["surface"])
        bar.grid(row=0, column=0, sticky="ew")
        self._sum = {}
        for i, (key, cap) in enumerate((("projects", t("cr.sum.projects")), ("teams", t("cr.sum.teams")),
                                        ("subagents", t("cr.sum.subagents")), ("tasks", t("cr.sum.tasks")),
                                        ("stuck", t("cr.sum.stuck")))):
            cell = tk.Frame(bar, bg=th["surface"])
            cell.pack(side="left", padx=(pad, int(8 * S)), pady=int(8 * S))
            var = tk.StringVar(master=win, value="0")
            lbl = tk.Label(cell, textvariable=var, bg=th["surface"], fg=th["fg"], font=self._font("f_big"))
            lbl.pack(anchor="w")
            tk.Label(cell, text=cap, bg=th["surface"], fg=th["muted"], font=self._font("f_xs")).pack(anchor="w")
            self._sum[key] = (var, lbl)
        tk.Frame(win, bg=th["line"], height=1).grid(row=0, column=0, sticky="sew")

        # thân: cây bên trái, chi tiết bên phải
        body = tk.Frame(win, bg=th["bg"])
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self._style()
        left = tk.Frame(body, bg=th["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(pad, 0), pady=pad)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        tree = self.tree = ttk.Treeview(left, style="Cr.Treeview", columns=("state", "live"), show="tree headings",
                                        selectmode="browse")
        tree.heading("#0", text=t("cr.col.tree"), anchor="w")
        tree.heading("state", text=t("cr.col.state"), anchor="w")
        tree.heading("live", text=t("cr.col.live"), anchor="w")
        tree.column("#0", width=int(340 * S), stretch=True)
        tree.column("state", width=int(110 * S), stretch=False)
        tree.column("live", width=int(260 * S), stretch=False)
        sb = ttk.Scrollbar(left, orient="vertical", command=tree.yview, style="Cr.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        for st, tag in STATE_TAG.items():
            tree.tag_configure(tag, foreground={"running": th["green"], "stuck": th["yellow"], "failed": th["red"],
                                                "done": th["muted"]}.get(st, th["faint"]))
        self._empty = tk.Label(tree, text=t("cr.empty"), bg=th["surface"], fg=th["muted"],
                               font=self._font("f_sm"))
        tree.bind("<<TreeviewSelect>>", lambda e: self._show_detail())
        tree.bind("<Double-1>", self._on_double)          # bấm đơn chỉ chọn; bấm đúp hoặc Enter mới focus session
        tree.bind("<Return>", lambda e: self._activate(self._selected()))

        right = tk.Frame(body, bg=th["surface"], width=int(300 * S))
        right.grid(row=0, column=1, sticky="ns", padx=pad, pady=pad)
        right.grid_propagate(False)
        self._detail_title, self._detail = tk.StringVar(master=win), tk.StringVar(master=win)
        tk.Label(right, textvariable=self._detail_title, bg=th["surface"], fg=th["fg"], font=self._font("f_title"),
                 anchor="w", justify="left", wraplength=int(272 * S)).pack(fill="x", padx=pad, pady=(pad, int(6 * S)))
        tk.Label(right, textvariable=self._detail, bg=th["surface"], fg=th["fg2"], font=self._font("f_sm"),
                 anchor="nw", justify="left", wraplength=int(272 * S)).pack(fill="both", expand=True, padx=pad)

        self._struct = self._live = None
        self._show_detail()
        win.lift()
        win.focus_force()

    def _style(self):
        th, S = self.th, self.S
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")    # theme mặc định của macOS (aqua) bỏ qua màu nền; app không dùng ttk ở chỗ khác
        except tk.TclError:
            pass
        try:
            rh = int(tkfont.Font(root=self.root, font=self._font("f_sm")).metrics("linespace") * 1.6)
        except tk.TclError:
            rh = int(24 * S)
        st.configure("Cr.Treeview", background=th["surface"], fieldbackground=th["surface"], foreground=th["fg"],
                     borderwidth=1, bordercolor=th["line"], lightcolor=th["surface"], darkcolor=th["surface"],
                     rowheight=rh, font=self._font("f_sm"))
        st.map("Cr.Treeview", background=[("selected", th["sel"])], foreground=[("selected", th["fg"])])
        st.configure("Cr.Treeview.Heading", background=th["bg"], foreground=th["muted"], borderwidth=0,
                     relief="flat", font=self._font("f_xs"))
        st.map("Cr.Treeview.Heading", background=[("active", th["bg"])])
        st.configure("Cr.Vertical.TScrollbar", background=th["line"], troughcolor=th["bg"], borderwidth=0,
                     arrowcolor=th["muted"])

    # ---------- cập nhật
    def _apply(self, rows):
        struct, live = struct_sig(rows), live_sig(rows)
        if struct != self._struct:
            self._rebuild(rows)
        elif live != self._live:
            self._update_live(rows)
        self._struct, self._live = struct, live
        sc = summary_counts(self._org)
        for key, (var, lbl) in self._sum.items():
            var.set(str(sc[key]))
        self._sum["stuck"][1].configure(fg=self.th["yellow"] if sc["stuck"] else self.th["fg"])
        if rows:
            self._empty.place_forget()
        else:
            self._empty.place(relx=0.5, rely=0.4, anchor="center")
        self._show_detail()

    @staticmethod
    def _is_open(v) -> bool:
        return v is True or str(v).lower() in ("1", "true")

    def _rebuild(self, rows):
        """Dựng lại cây; giữ chọn, trạng thái đóng/mở (theo key ổn định) và vị trí cuộn."""
        tree = self.tree
        sel = tree.selection()
        sel_key = self._rows[sel[0]]["key"] if sel and sel[0] in self._rows else None
        opened = {self._rows[i]["key"]: self._is_open(tree.item(i, "open")) for i in self._rows}
        top = tree.yview()[0]
        tree.delete(*tree.get_children(""))
        self._rows, self._iid_of, self._vals = {}, {}, {}
        for r in rows:
            self._counter += 1
            iid = f"i{self._counter}"
            vals = (r["summary"], live_text(r))
            tag = row_tag(r)
            tree.insert(self._iid_of.get(r["parent"], ""), "end", iid=iid, text=r["name"], values=vals,
                        tags=(tag,) if tag else (), open=opened.get(r["key"], True))
            self._rows[iid], self._iid_of[r["key"]], self._vals[iid] = r, iid, vals
        if sel_key in self._iid_of:
            tree.selection_set(self._iid_of[sel_key])
        tree.yview_moveto(top)
        self._rebuilds += 1

    def _update_live(self, rows):
        """Cấu trúc không đổi: chỉ ghi lại nhãn cột đã đổi, giữ nguyên iid, chọn và đóng/mở."""
        for r in rows:
            iid = self._iid_of[r["key"]]
            self._rows[iid] = r
            vals = (r["summary"], live_text(r))
            if vals != self._vals[iid]:
                self.tree.item(iid, values=vals)
                self._vals[iid] = vals

    def _show_detail(self):
        r = self._rows.get(self._selected())
        if r is None:
            self._detail_title.set(t("cr.detail"))
            self._detail.set(t("cr.detail.hint"))
        else:
            self._detail_title.set(r["name"])
            self._detail.set("\n".join(f"{k}: {v}" for k, v in r["detail"] if v))

    # ---------- tương tác
    def _selected(self):
        sel = self.tree.selection() if self.tree is not None else ()
        return sel[0] if sel else None

    def _on_double(self, ev):
        try:
            if self.tree.identify_region(ev.x, ev.y) not in ("tree", "cell") \
                    or "indicator" in self.tree.identify_element(ev.x, ev.y):
                return
            self._activate(self.tree.identify_row(ev.y))
        except tk.TclError:
            pass

    def _activate(self, iid):
        """Bấm đúp hoặc Enter trên session thì focus cửa sổ của nó; subagent, task nền và nhóm chỉ để xem."""
        r = self._rows.get(iid)
        if r is not None and r["kind"] == "session" and r["session_id"]:
            try:
                self._focus(r["session_id"])
            except Exception as e:
                self._report("focus_session: " + repr(e)[:200])
