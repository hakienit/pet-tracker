"""Bộ chuyển đổi Layout của board -> payload `/api/layout` của viewer 3D: hàm thuần `viewer_payload(...)`.

Spec: docs/specs/2026-10-30-3d-viewer-design.md (mục "Bộ chuyển đổi `viewer_payload`", S21, S22, S25, Quyết định P, AA).

Không import tkinter/os/subprocess/pathlib/socket/http/threading, không đọc đĩa, không sinh ngẫu nhiên, không sửa đối số.
Đầu ra chỉ gồm dict, list, str, int, float hữu hạn, bool, None; mọi khoá thuộc allowlist, mọi state là enum đóng.
"""
from __future__ import annotations

import hmac
import re

from . import office, org
from .mascots import MOODS

MAX_NODES = 1000
FLOOR_GAP = 6

_PITCH = office.FLOOR_CLUSTER_COLS * office.CLUSTER_W + FLOOR_GAP
_DESK_ST = tuple(office.STATE_STYLE["desk"])
_WORKER_ST = tuple(office.STATE_STYLE["worker"])
_MARKERS = ("ring", "cross")
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
_SEP = re.compile(r"[/\\]")
# ngoài org._CTRL: surrogate lẻ (UTF-8 chặt hỏng) và ký tự vô hình
_INVIS = re.compile("[\ud800-\udfff\u00ad\u180e\u2060-\u2064\ufff9-\ufffb\U000e0000-\U000e007f]")
_TOKENS_MAX = 2 ** 53 - 1      # số nguyên lớn nhất JS đọc đúng


# ---------------------------------------------------------------- đọc đầu vào không tin cậy
def _text(v, n) -> str:
    # làm sạch rồi mới cắt; không cắt thô trước: mọi chuỗi trong org.build đã qua org._s (<= org.MAX_STR)
    return _INVIS.sub("", org._CTRL.sub("", v))[:n] if isinstance(v, str) else ""


def _int(v) -> int:
    return v if type(v) is int and v > 0 else 0


def _coord(v) -> int:
    return v if type(v) is int else 0


def _list(d, name) -> list:
    v = d.get(name) if isinstance(d, dict) else None
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _hex(theme, name) -> str:
    for v in (theme.get(name) if isinstance(name, str) else None, theme.get("idle")):
        if isinstance(v, str) and _HEX.fullmatch(v):
            return v.lower()
    return "#000000"


def _worker(org_out, ref):
    """Worker trong `org_out` theo `ref` [pi, ti, si, wi]; ref hỏng thì {}."""
    if not (isinstance(ref, list) and len(ref) == 4 and all(type(i) is int and i >= 0 for i in ref)):
        return {}
    cur = org_out
    for name, i in zip(("projects", "teams", "sessions", "workers"), ref):
        seq = cur.get(name) if isinstance(cur, dict) else None
        if not isinstance(seq, list) or i >= len(seq):
            return {}
        cur = seq[i]
    return cur if isinstance(cur, dict) else {}


def _team_label(top) -> str:
    top = top if isinstance(top, str) else ""
    return _SEP.split(top.rstrip("/\\"))[-1] or top


# ---------------------------------------------------------------- viewer_payload
def viewer_payload(layout, org_out, theme, mascot_ids, key_secret) -> dict:
    if not isinstance(layout, dict) or layout.get("version") != 1:
        raise ValueError("layout không phải Layout version 1")
    if not isinstance(key_secret, bytes) or len(key_secret) < 16:
        raise ValueError("key_secret phải là bytes, tối thiểu 16 byte")

    def key(s) -> str:
        # = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()[:16]; hmac.digest một lượt nhanh gần gấp đôi (Đ2)
        return hmac.digest(key_secret, s.encode("utf-8", "surrogatepass"), "sha256").hex()[:16]

    def mascot(node, seed):
        i = office.mascot_index(seed, len(mascot_ids)) if type(seed) is int and seed >= 0 else None
        if i is not None:
            node["mascot"] = mascot_ids[i]

    styles = layout.get("styles") if isinstance(layout.get("styles"), dict) else {}
    legend = {}
    for part, enum in (("desk", _DESK_ST), ("worker", _WORKER_ST)):
        tbl = styles.get(part) if isinstance(styles.get(part), dict) else {}
        legend[part] = {}
        for st in enum:
            s = tbl.get(st) if isinstance(tbl.get(st), dict) else {}
            legend[part][st] = {"color": _hex(theme, s.get("color")),
                                "mood": s.get("mood") if s.get("mood") in MOODS else "idle",
                                "marker": s.get("marker") if s.get("marker") in _MARKERS else None}

    nodes, live = [], {}

    def add(lkey, kind, parent, x, y, w, h, state=None, label="", sub=""):
        n = {"key": key(lkey), "kind": kind, "parent": parent, "x": x, "y": y, "w": w, "h": h, "state": state,
             "label": label, "sub": sub}
        nodes.append(n)
        return n

    # sàn theo level: level hợp lệ và duy nhất đặt trước; sai kiểu hoặc trùng thì max(level đã dùng) + 1
    good, bad = {}, []
    for f in _list(layout, "floors"):
        lv = f.get("level")
        if type(lv) is int and lv >= 0 and lv not in good:
            good[lv] = f
        else:
            bad.append(f)
    placed = sorted(good.items())
    for f in bad:
        placed.append((max((lv for lv, _ in placed), default=-1) + 1, f))
    used = [lv for lv, _ in placed]
    for lv, f in placed:
        ox = lv * _PITCH
        fn = add(f.get("key"), "project", None, ox, 0, _coord(f.get("w")), _coord(f.get("h")),
                 label=_text(f.get("name"), 60))
        for c in _list(f, "clusters"):
            br = c.get("branch")
            cn = add(c.get("key"), "team", fn["key"], ox + _coord(c.get("x")), _coord(c.get("y")), _coord(c.get("w")),
                     _coord(c.get("h")), label=_text(_team_label(c.get("top")), 60), sub=_text(br, 120))
            for d in _list(c, "desks"):
                dx, dy, dw, dh = ox + _coord(d.get("x")), _coord(d.get("y")), _coord(d.get("w")), _coord(d.get("h"))
                st = d.get("state")
                name, sid = d.get("name"), d.get("session_id")
                if isinstance(sid, str) and sid and name == sid[:8]:
                    name = ""                                 # tên dự phòng sid[:8] của claude_data: S21 cấm session id
                dn = add(d.get("key"), "session", cn["key"], dx, dy, dw, dh, st if st in _DESK_ST else "idle",
                         _text(name, 60))
                mascot(dn, d.get("seed"))
                al = d.get("alert")
                if _int(al.get("stuck") if isinstance(al, dict) else None):
                    dn["alert"] = al["stuck"]
                for w in _list(d, "workers"):
                    st, src = w.get("state"), _worker(org_out, w.get("ref"))
                    wn = add(w.get("key"), "subagent", dn["key"], ox + _coord(w.get("x")), _coord(w.get("y")), 1, 1,
                             st if st in _WORKER_ST else "unknown", _text(w.get("department"), 60),
                             _text(src.get("description"), 120))
                    mascot(wn, w.get("seed"))
                    live.setdefault(wn["key"], {"tokens": min(_int(src.get("tokens")), _TOKENS_MAX),
                                                "started": org._num(src.get("started")),
                                                "last_activity": org._num(src.get("last_activity"))})
                for v in _list(d, "devices"):
                    st = v.get("state")
                    vn = add(v.get("key"), "bgtask", dn["key"], ox + _coord(v.get("x")), _coord(v.get("y")), 1, 1,
                             st if st in _WORKER_ST else "unknown")
                    live.setdefault(vn["key"], {"started": org._num(_worker(org_out, v.get("ref")).get("started"))})
                more = d.get("more") if isinstance(d.get("more"), dict) else {}
                if _int(more.get("n")):
                    counts = {}
                    raw = more.get("counts") if isinstance(more.get("counts"), dict) else {}
                    for k, n in raw.items():
                        k = k if k in _WORKER_ST else "unknown"
                        if _int(n):
                            counts[k] = counts.get(k, 0) + n
                    on = add("%s/more" % d.get("key"), "overflow", dn["key"], dx, dy, dw, dh)
                    on["count"], on["counts"] = more["n"], counts
    gm = layout.get("more") if isinstance(layout.get("more"), dict) else {}
    if _int(gm.get("desks")):
        on = add("more:desks", "overflow", None, (max(used, default=-1) + 1) * _PITCH, 0, 2, 2)
        on["count"] = gm["desks"]
        if _int(gm.get("stuck_desks")):
            on["alert"] = gm["stuck_desks"]

    # va chạm key (tình cờ 64 bit): giữ nút đầu; rồi trần MAX_NODES cắt từ cuối (cha luôn đứng trước con)
    seen, kept = set(), []
    for n in nodes:
        if n["key"] not in seen:
            seen.add(n["key"])
            kept.append(n)
    hidden = max(0, len(kept) - MAX_NODES)
    kept = kept[:MAX_NODES]
    keys = {n["key"] for n in kept}
    return {"schema": 1,
            "bounds": {"w": max((n["x"] + n["w"] for n in kept), default=0),
                       "h": max((n["y"] + n["h"] for n in kept), default=0)},
            "palette": {"bg": _hex(theme, "bg"), "floor": _hex(theme, "surf"), "team": _hex(theme, "track"),
                        "line": _hex(theme, "line"), "fg": _hex(theme, "fg"), "warn": _hex(theme, "warn"),
                        "danger": _hex(theme, "danger")},
            "legend": legend,
            "more": {"desks": _int(gm.get("desks")), "stuck_desks": _int(gm.get("stuck_desks"))},
            "hidden": hidden,
            "nodes": kept,
            "live": {k: v for k, v in live.items() if k in keys}}
