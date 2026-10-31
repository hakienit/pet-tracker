"""Board: tab 2.5D của Control room, vẽ Layout của `office.office_layout` thành văn phòng isometric.

Phần này chỉ gồm hàm thuần (không Tk, kiểm bằng unit test): thứ tự vẽ, ba chữ ký, chọn sàn, cảnh báo sàn, chi tiết của
từng mục. Số liệu (token, thời gian) tra từ `org_out` qua `ref` của nút; chi tiết session/subagent/task nền gọi đúng
hàm của cây (`control_room.session_detail`...). Mọi chuỗi hiển thị đã qua `sanitize()`.
"""
from __future__ import annotations

from . import office
from .control_room import (MAX_NAME, _i, _team_label, bgtask_detail, counts_text, sanitize, session_detail,
                           state_label, subagent_detail)
from .i18n import t

try:
    import tkinter as tk
except ImportError:      # Python không có Tk: hàm thuần vẫn dùng/kiểm được
    tk = None

MAX_DESK_NAME = 24      # nhãn dưới pod; tiêu đề panel cắt theo MAX_NAME như cây
MORE_DESKS_KEY = ("chip", "desks")  # khoá chip là tuple nên không bao giờ trùng khoá chuỗi của nút
_RANK = {"desk": 0, "device": 1, "mascot": 2, "worker": 2}   # trong cùng một ô: mặt bàn, device, rồi mascot


def chip_key(desk) -> tuple:
    return "chip", desk["key"]


def desk_name(desk, limit=MAX_DESK_NAME) -> str:
    return sanitize(desk.get("name"), limit) or t("cr.anon_session")


def cluster_label(c) -> str:
    return _team_label(sanitize(c.get("top")), sanitize(c.get("branch"), 80))


def _desks(floor):
    return [d for c in floor["clusters"] for d in c["desks"]] if floor else []


def paint_order(floor) -> list:
    """[(kind, nút)] theo thứ tự painter: x + y tăng, hoà theo x, rồi `_RANK`, rồi khoá. kind: desk (mặt bàn),
    mascot (mascot ngồi ở ô (desk.x, desk.y)), device, worker."""
    items = []
    for d in _desks(floor):
        items += [("desk", d), ("mascot", d)]
        items += [("worker", w) for w in d["workers"]] + [("device", v) for v in d["devices"]]
    return sorted(items, key=lambda kn: (kn[1]["x"] + kn[1]["y"], kn[1]["x"], _RANK[kn[0]], kn[1]["key"]))


# ---------------------------------------------------------------- chữ ký (xem spec "Vòng cập nhật")
def board_struct_sig(layout, floor) -> tuple:
    sig = [(floor["key"], floor["w"], floor["h"]) if floor else None, layout["more"]["desks"]]
    for c in floor["clusters"] if floor else ():
        sig.append((c["key"], c["x"], c["y"], cluster_label(c)))
        for d in c["desks"]:
            sig.append((d["key"], d["x"], d["y"], d["seed"], desk_name(d), d["more"]["n"]))
            sig += [(w["key"], w["x"], w["y"], w.get("seed")) for w in d["workers"] + d["devices"]]
    return tuple(sig)


def board_style_sig(layout, floor) -> tuple:
    sig = [layout["more"]["stuck_desks"] > 0]
    for d in _desks(floor):
        sig.append((d["key"], d["state"], d["alert"]["stuck"], "stuck" in d["more"]["counts"]))
        sig += [(w["key"], w["state"]) for w in d["workers"] + d["devices"]]
    return tuple(sig)


def board_live_sig(layout, floor, org_out, now, key=None) -> tuple:
    return floor_nav(layout, floor, org_out), node_detail(layout, floor, key, org_out, now)


# ---------------------------------------------------------------- sàn
def floor_alerts(layout) -> dict:
    """{khoá sàn: số subagent stuck} của các sàn có stuck (tính cả worker không vẽ, qua `alert.stuck`)."""
    out = {}
    for f in layout["floors"]:
        n = sum(d["alert"]["stuck"] for d in _desks(f))
        if n:
            out[f["key"]] = n
    return out


def _running(floor) -> bool:
    return any(w["state"] == "running" for d in _desks(floor) for w in d["workers"] + d["devices"]) or \
        any(d["more"]["counts"].get("running") for d in _desks(floor))


def pick_floor(layout, chosen=None):
    """Sàn đang chọn nếu còn; không thì sàn đầu tiên có stuck, rồi có running, rồi level thấp nhất. Không sàn: None."""
    floors = layout["floors"]
    alerts = floor_alerts(layout)
    for test in (lambda f: f["key"] == chosen, lambda f: f["key"] in alerts, _running, lambda f: True):
        for f in floors:
            if test(f):
                return f
    return None


def _ref(org_out, ref):
    """Dict nguồn trong org_out theo `ref` ([pi], [pi, ti], [pi, ti, si], [pi, ti, si, wi]); hỏng thì None."""
    cur = org_out
    for name, i in zip(("projects", "teams", "sessions", "workers"), ref or ()):
        items = cur.get(name) if isinstance(cur, dict) else None
        if not isinstance(items, list) or not isinstance(i, int) or not 0 <= i < len(items):
            return None
        cur = items[i]
    return cur if isinstance(cur, dict) else None


def _counts_line(c) -> str:
    c = c if isinstance(c, dict) else {}
    sub = c.get("subagent") if isinstance(c.get("subagent"), dict) else {}
    task = c.get("bgtask") if isinstance(c.get("bgtask"), dict) else {}
    return counts_text(_i(sub.get("running")) + _i(sub.get("stuck")), _i(task.get("running")), _i(sub.get("stuck")))


def floor_nav(layout, floor, org_out) -> tuple:
    """(i, n, tên project, counts_text của project, có sàn khác đang có stuck)."""
    floors = layout["floors"]
    if floor not in floors:
        return 0, len(floors), "", "", bool(floor_alerts(layout))
    root = sanitize(floor.get("root"))
    p = _ref(org_out, floor.get("ref")) or {}
    return (floors.index(floor) + 1, len(floors), sanitize(floor.get("name"), MAX_NAME) or root or t("cr.unknown"),
            _counts_line(p.get("counts")), any(k != floor["key"] for k in floor_alerts(layout)))


# ---------------------------------------------------------------- chi tiết (panel bên phải)
def node_detail(layout, floor, key, org_out, now):
    """(tiêu đề, [(nhãn, giá trị)]) của mục có khoá `key` trên sàn; không thấy hoặc nguồn hỏng thì None.
    Dòng có giá trị None là câu đầy đủ, panel chỉ in nhãn ("" vẫn nghĩa là ẩn dòng, như cây)."""
    if key is None:
        return None
    if key == MORE_DESKS_KEY:
        n, stuck = layout["more"]["desks"], layout["more"]["stuck_desks"]
        if not n:
            return None
        rows = [(t("cr.board.more_detail"), str(n)), (t("cr.board.cap", n=layout["limits"]["desks"]), None)]
        return t("cr.board.more_desks", n=n), rows + ([(t("cr.board.stuck_desks", n=stuck), None)] if stuck else [])
    for d in _desks(floor):
        if key == chip_key(d):
            counts = d["more"]["counts"]
            return t("cr.board.more_detail"), [(state_label(s) or t("cr.unknown"), str(counts[s]))
                                               for s in office.STATE_STYLE["worker"] if counts.get(s)]
        if key == d["key"]:
            s = _ref(org_out, d["ref"])
            return None if s is None else (desk_name(d, MAX_NAME), session_detail(s, now) +
                                           [(t("cr.f.workers"), _counts_line(s.get("counts")))])
        for w in d["workers"]:
            if key == w["key"]:
                src = _ref(org_out, w["ref"])
                if src is None:
                    return None
                title = sanitize(src.get("description"), MAX_NAME) or sanitize(src.get("type"), 80) or t("cr.anon_subagent")
                return title, subagent_detail(src, now)
        for v in d["devices"]:
            if key == v["key"]:
                src = _ref(org_out, v["ref"])
                return None if src is None else (t("cr.bg_task", id=sanitize(src.get("id"), 24)), bgtask_detail(src, now))
    return None
