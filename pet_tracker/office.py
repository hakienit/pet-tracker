"""Layout văn phòng cho Board 2.5D và viewer 3D: hàm thuần `office_layout(org_out, cfg, prev=None)`.

Spec: docs/specs/2026-10-30-board-2-5d-design.md (mục "Layout chung", "Bảng state -> hiển thị", "Cấu hình").

Không import tkinter/os/subprocess/pathlib, không đọc đĩa, không cache, không câu lệnh `global`, không sửa đối số.
Layout chỉ gồm dict, list, str, int, bool, None. `prev` là Layout của lần gọi trước: bộ nhớ gán ô nằm trong Layout.
Hằng cấp module bất biến (số, tuple) trừ hai bảng STATE_STYLE và ALERT_STYLE; Layout["styles"] là bản sao.
"""
from __future__ import annotations

import math
import zlib

VERSION = 1

# ---------------------------------------------------------------- hằng hình học (viewer 3D dùng cùng giá trị)
POD = 4
POD_STRIDE = 5
CLUSTER_PODS = (3, 2)          # pod theo x, y trong một cụm: tối đa 6 bàn
CLUSTER_W = 15
CLUSTER_H = 10
FLOOR_CLUSTER_COLS = 2
DEVICE_SLOTS = 3
# lane -> ô -> (dx, dy) so với gốc pod; 4 lane phủ đúng 12 ô vòng ngoài pod
LANES = (((0, 0), (1, 0), (2, 0)), ((3, 0), (3, 1), (3, 2)), ((3, 3), (2, 3), (1, 3)), ((0, 3), (0, 2), (0, 1)))
_DEVICE_CELLS = ((1, 0), (0, 1), (1, 1))   # so với (desk.x, desk.y)

MAX_DESKS_CEIL = 200
MAX_WORKERS_CEIL = 12
_PODS = CLUSTER_PODS[0] * CLUSTER_PODS[1]
_DESK_STATES = ("idle", "run", "wait", "done")
_WORKER_STATES = ("running", "stuck", "done", "failed", "killed", "ended", "unknown")
_ALIVE = ("running", "stuck")

# ---------------------------------------------------------------- bảng state (một nguồn duy nhất)
STATE_STYLE = {
    "desk": {
        "idle": {"color": "idle", "mood": "idle", "marker": None},
        "run": {"color": "run", "mood": "run", "marker": None},
        "wait": {"color": "wait", "mood": "wait", "marker": None},
        "done": {"color": "done", "mood": "done", "marker": None},
    },
    "worker": {
        "running": {"color": "ok", "mood": "run", "marker": None},
        "stuck": {"color": "warn", "mood": "wait", "marker": "ring"},
        "done": {"color": "mut", "mood": "done", "marker": None},
        "failed": {"color": "danger", "mood": "quota", "marker": "cross"},
        "killed": {"color": "idle", "mood": "idle", "marker": None},
        "ended": {"color": "idle", "mood": "idle", "marker": None},
        "unknown": {"color": "idle", "mood": "idle", "marker": None},
    },
}
ALERT_STYLE = {"color": "warn", "marker": "ring"}


def _styles() -> dict:
    return {part: {st: dict(v) for st, v in tbl.items()} for part, tbl in STATE_STYLE.items()}


# ---------------------------------------------------------------- hàm xuất nhỏ
def valid_org(org_out) -> bool:
    return isinstance(org_out, dict) and isinstance(org_out.get("projects"), list)


def mascot_index(seed, count):
    return None if count <= 0 else seed % count


def max_floor_h(desks) -> int:
    return CLUSTER_H * -(-desks // FLOOR_CLUSTER_COLS)


# ---------------------------------------------------------------- đọc đầu vào không tin cậy
def _str(v) -> str:
    return v if isinstance(v, str) else ""


def _num(v):
    """float hữu hạn hoặc None (bool không phải số)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            f = float(v)
        except OverflowError:
            return None
        if math.isfinite(f):
            return f
    return None


def _clamp(v, default, lo, hi) -> int:
    n = _num(v)
    if n is None:
        return default
    return max(lo, min(hi, int(n)))


def _crc(s: str) -> int:
    return zlib.crc32(s.encode("utf-8", "surrogatepass")) & 0xFFFFFFFF


def _uniq(seen: set, base: str) -> str:
    """Khoá trùng trong cùng cấp thêm #1, #2... theo thứ tự đầu vào."""
    k, n = base, 0
    while k in seen:
        n += 1
        k = "%s#%d" % (base, n)
    seen.add(k)
    return k


def _wstate(v) -> str:
    return v if isinstance(v, str) and v in _WORKER_STATES else "unknown"


def _dstate(v) -> str:
    if v == "error":
        return "wait"
    return v if isinstance(v, str) and v in _DESK_STATES else "idle"


def _parse(org_out) -> list:
    """Cây trung gian [floor{clusters[{desks[...]}]}] của các nhánh hợp lệ, khoá đã gán, theo thứ tự đầu vào."""
    floors, fseen = [], set()
    for pi, p in enumerate(org_out["projects"]):
        if not isinstance(p, dict) or not isinstance(p.get("teams"), list):
            continue
        root = _str(p.get("root"))
        fkey = _uniq(fseen, "p:" + root)
        floor = {"key": fkey, "name": _str(p.get("name")), "root": root, "ref": [pi], "clusters": []}
        cseen = set()
        for ti, t in enumerate(p["teams"]):
            if not isinstance(t, dict) or not isinstance(t.get("sessions"), list):
                continue
            top = _str(t.get("top"))
            ckey = _uniq(cseen, fkey + "/t:" + top)
            br = t.get("branch")
            cl = {"key": ckey, "top": top, "branch": br if isinstance(br, str) else None, "ref": [pi, ti],
                  "desks": []}
            dseen = set()
            for si, s in enumerate(t["sessions"]):
                if not isinstance(s, dict):
                    continue
                sid = _str(s.get("session_id"))
                dkey = _uniq(dseen, ckey + "/s:" + sid)
                d = {"key": dkey, "sid": sid, "name": _str(s.get("name")), "state": _dstate(s.get("state")),
                     "started": _num(s.get("started_at")), "ref": [pi, ti, si], "subs": [], "bgs": [], "stuck": 0}
                wseen = set()
                ws = s.get("workers")
                for wi, w in enumerate(ws if isinstance(ws, list) else []):
                    if not isinstance(w, dict):
                        continue
                    kind, wid, st = w.get("kind"), _str(w.get("id")), _wstate(w.get("state"))
                    if kind == "subagent":
                        d["subs"].append({"key": _uniq(wseen, dkey + "/w:sub:" + wid), "id": wid, "state": st,
                                          "dept": _str(w.get("department")), "started": _num(w.get("started")),
                                          "last": _num(w.get("last_activity")), "ref": [pi, ti, si, wi]})
                        d["stuck"] += st == "stuck"
                    elif kind == "bgtask":
                        d["bgs"].append({"key": _uniq(wseen, dkey + "/w:bg:" + wid), "id": wid, "state": st,
                                         "started": _num(w.get("started")), "ref": [pi, ti, si, wi]})
                cl["desks"].append(d)
            floor["clusters"].append(cl)
        floors.append(floor)
    return floors


# ---------------------------------------------------------------- slot của lần trước
def _int_in(v, lo, hi):
    return v if type(v) is int and lo <= v < hi else None


def _prev_slots(prev, limits) -> dict:
    """Bản đồ khoá -> slot từ Layout `prev`; `prev` hỏng, sai version hoặc khác `limits` thì rỗng (như None)."""
    out = {k: {} for k in ("floor", "cluster", "desk", "worker", "device")}
    if not (isinstance(prev, dict) and prev.get("version") == VERSION and prev.get("limits") == limits
            and isinstance(prev.get("floors"), list)):
        return out
    nd = limits["desks"]

    def put(kind, node, value):
        if isinstance(node, dict) and isinstance(node.get("key"), str) and value is not None:
            out[kind].setdefault(node["key"], value)

    def each(node, name):
        v = node.get(name) if isinstance(node, dict) else None
        return v if isinstance(v, list) else []

    for f in prev["floors"]:
        put("floor", f, _int_in(f.get("level") if isinstance(f, dict) else None, 0, nd))
        for c in each(f, "clusters"):
            put("cluster", c, _int_in(c.get("slot") if isinstance(c, dict) else None, 0, nd))
            for d in each(c, "desks"):
                put("desk", d, _int_in(d.get("slot") if isinstance(d, dict) else None, 0, _PODS))
                for w in each(d, "workers"):
                    ln = _int_in(w.get("lane") if isinstance(w, dict) else None, 0, len(LANES))
                    sl = _int_in(w.get("slot") if isinstance(w, dict) else None, 0, len(LANES[0]))
                    put("worker", w, None if ln is None or sl is None else (ln, sl))
                for v in each(d, "devices"):
                    put("device", v, _int_in(v.get("slot") if isinstance(v, dict) else None, 0, DEVICE_SLOTS))
    return out


def _lowest_free(used) -> int:
    n = 0
    while n in used:
        n += 1
    return n


# ---------------------------------------------------------------- worker và device quanh một bàn
def _order(w):
    """Thứ tự xử lý worker: (running và stuck trước, started tăng dần với None cuối, id)."""
    return w["state"] not in _ALIVE, w["started"] is None, w["started"] or 0.0, w["id"], w["key"]


def _place_workers(subs, prev_slots, cap):
    """Trả (cells[lane][slot] -> worker|None, danh sách worker không vẽ)."""
    cells = [[None] * len(LANES[0]) for _ in LANES]
    more, drawn = [], 0

    def owner(lane):
        return next((c["dept"] for c in cells[lane] if c is not None), None)

    def place(w):                                             # 4. một worker mới; worker bị thay vào `more`
        nonlocal drawn
        if drawn < cap:
            for ln in range(len(LANES)):                      # a. ô trống thấp nhất trong lane của phòng ban
                if owner(ln) == w["dept"] and None in cells[ln]:
                    cells[ln][cells[ln].index(None)] = w
                    drawn += 1
                    return True
            for ln in range(len(LANES)):                      # b. ô 0 của lane không chủ thấp nhất
                if owner(ln) is None:
                    cells[ln][0] = w
                    drawn += 1
                    return True
        # c, d chỉ cho worker còn sống: worker đã xong mà thay được nhau thì cùng đầu vào sẽ đổi chỗ vòng tròn
        if w["state"] not in _ALIVE:
            return False
        cand = [(c["last"] or 0.0, c["key"], ln, sl) for ln in range(len(LANES)) if owner(ln) == w["dept"]
                for sl, c in enumerate(cells[ln]) if c is not None and c["state"] not in _ALIVE]
        if cand:                                              # c. thay worker đã xong có last_activity nhỏ nhất
            _, _, ln, sl = min(cand)
            more.append(cells[ln][sl])
            cells[ln][sl] = w
            return True
        for ln in range(len(LANES)):                          # d. giải phóng lane thấp nhất chỉ có worker đã xong
            ws = [c for c in cells[ln] if c is not None]
            if ws and all(c["state"] not in _ALIVE for c in ws):
                more.extend(ws)
                cells[ln] = [w] + [None] * (len(LANES[0]) - 1)
                drawn += 1 - len(ws)
                return True
        return False

    queue = []
    for w in sorted(subs, key=_order):                        # 1. giữ ô đã gán
        p = prev_slots.get(w["key"])
        if p is not None and drawn < cap and cells[p[0]][p[1]] is None and owner(p[0]) in (None, w["dept"]):
            cells[p[0]][p[1]] = w
            drawn += 1
        else:
            queue.append(w)
    # Lặp tới khi một lượt không đặt thêm ai: 4d giải phóng nhiều ô hơn số nó dùng, phần dư phải được xét lại ngay,
    # nếu không lần gọi sau (cùng đầu vào) sẽ đặt chúng và Layout đổi. Lượt cuối không đổi gì nên lần gọi sau lặp lại
    # đúng lượt đó. Dừng vì worker sống không bị thay và ô trống mới chỉ sinh ra khi một worker sống được đặt.
    for _ in range(len(subs) + len(LANES) * len(LANES[0]) + 1):  # chặn trên: hồi quy thành lỗi thay vì treo UI
        more, progressed = [], False
        for w in sorted(queue, key=_order):
            if place(w):
                progressed = True
            else:
                more.append(w)                                # e.
        if not progressed:
            return cells, more
        queue = more
    raise AssertionError("_place_workers không dừng")


def _place_devices(bgs, prev_slots):
    cells, more = [None] * DEVICE_SLOTS, []
    order = sorted(bgs, key=lambda v: (v["state"] != "running", v["started"] is None, v["started"] or 0.0,
                                        v["id"], v["key"]))
    fresh = []
    for v in order:
        p = prev_slots.get(v["key"])
        if p is not None and cells[p] is None:
            cells[p] = v
        else:
            fresh.append(v)
    for v in fresh:
        if None in cells:
            cells[cells.index(None)] = v
            continue
        # chỉ device đang chạy mới thay được device khác (cùng lý do ở _place_workers)
        cand = [(c["started"] or 0.0, c["key"], i) for i, c in enumerate(cells) if c["state"] != "running"]
        if v["state"] == "running" and cand:
            i = min(cand)[2]
            more.append(cells[i])
            cells[i] = v
        else:
            more.append(v)
    return cells, more


# ---------------------------------------------------------------- office_layout
def _limits(cfg) -> dict:
    cfg = cfg if isinstance(cfg, dict) else {}
    return {"desks": _clamp(cfg.get("board_max_desks"), 48, 1, MAX_DESKS_CEIL),
            "workers": _clamp(cfg.get("board_max_workers"), 12, 0, MAX_WORKERS_CEIL),
            "devices": DEVICE_SLOTS}


def _assign_desks(floors, slots, limits, more) -> dict:
    """Khoá bàn -> pod: giữ trước, rồi nhận bàn mới theo (started_at, None cuối, khoá); bàn dư đếm vào `more`."""
    pods, placed, drawn = {}, {}, 0
    pending = []
    for f in floors:
        for c in f["clusters"]:
            used = pods.setdefault(c["key"], set())
            for d in c["desks"]:
                p = slots["desk"].get(d["key"])
                if p is not None and p not in used and drawn < limits["desks"]:
                    used.add(p)
                    placed[d["key"]] = p
                    drawn += 1
                else:
                    pending.append((c["key"], d))
    pending.sort(key=lambda x: (x[1]["started"] is None, x[1]["started"] or 0.0, x[1]["key"]))
    for ckey, d in pending:
        used = pods[ckey]
        if len(used) < _PODS and drawn < limits["desks"]:
            p = _lowest_free(used)
            used.add(p)
            placed[d["key"]] = p
            drawn += 1
        else:
            more["desks"] += 1
            more["stuck_desks"] += d["stuck"] > 0
    return placed


def office_layout(org_out, cfg, prev=None) -> dict:
    limits = _limits(cfg)
    out = {"version": VERSION, "limits": limits, "styles": _styles(), "floors": [],
           "more": {"desks": 0, "stuck_desks": 0}}
    if not valid_org(org_out):
        return out
    floors = _parse(org_out)
    slots = _prev_slots(prev, limits)
    placed = _assign_desks(floors, slots, limits, out["more"])

    # --- sàn và cụm chỉ gồm nút có bàn vẽ; kept trước, mới theo (root | top, khoá)
    live = []
    for f in floors:
        cls = [(c, [d for d in c["desks"] if d["key"] in placed]) for c in f["clusters"]]
        cls = [(c, ds) for c, ds in cls if ds]
        if cls:
            live.append((f, cls))
    levels = {}
    taken = set()
    for f, _ in live:
        lv = slots["floor"].get(f["key"])
        if lv is not None and lv not in taken:
            levels[f["key"]] = lv
            taken.add(lv)
    for f, _ in sorted(live, key=lambda x: (x[0]["root"], x[0]["key"])):
        if f["key"] not in levels:
            levels[f["key"]] = _lowest_free(taken)
            taken.add(levels[f["key"]])

    for f, cls in sorted(live, key=lambda x: levels[x[0]["key"]]):
        cslot, taken = {}, set()
        for c, _ in cls:
            s = slots["cluster"].get(c["key"])
            if s is not None and s not in taken:
                cslot[c["key"]] = s
                taken.add(s)
        for c, _ in sorted(cls, key=lambda x: (x[0]["top"], x[0]["key"])):
            if c["key"] not in cslot:
                cslot[c["key"]] = _lowest_free(taken)
                taken.add(cslot[c["key"]])
        clusters = []
        for c, ds in sorted(cls, key=lambda x: cslot[x[0]["key"]]):
            cs = cslot[c["key"]]
            cx, cy = (cs % FLOOR_CLUSTER_COLS) * CLUSTER_W, (cs // FLOOR_CLUSTER_COLS) * CLUSTER_H
            desks = [_desk(d, placed[d["key"]], cx, cy, slots, limits) for d in sorted(ds, key=lambda x: placed[x["key"]])]
            clusters.append({"key": c["key"], "slot": cs, "top": c["top"], "branch": c["branch"], "x": cx, "y": cy,
                             "w": CLUSTER_W, "h": CLUSTER_H, "ref": c["ref"], "desks": desks})
        rows = max(c["slot"] for c in clusters) // FLOOR_CLUSTER_COLS + 1
        out["floors"].append({"key": f["key"], "level": levels[f["key"]], "name": f["name"], "root": f["root"],
                              "w": FLOOR_CLUSTER_COLS * CLUSTER_W, "h": CLUSTER_H * rows, "ref": f["ref"],
                              "clusters": clusters})
    return out


def _desk(d, pod, cx, cy, slots, limits) -> dict:
    ox, oy = cx + (pod % CLUSTER_PODS[0]) * POD_STRIDE, cy + (pod // CLUSTER_PODS[0]) * POD_STRIDE
    dx, dy = ox + 1, oy + 1
    cells, wmore = _place_workers(d["subs"], slots["worker"], limits["workers"])
    devs, dmore = _place_devices(d["bgs"], slots["device"])
    workers = [{"key": w["key"], "id": w["id"], "department": w["dept"], "slot": sl, "lane": ln,
                "x": ox + LANES[ln][sl][0], "y": oy + LANES[ln][sl][1], "state": w["state"], "seed": _crc(w["dept"]),
                "ref": w["ref"]}
               for ln, lane in enumerate(cells) for sl, w in enumerate(lane) if w is not None]
    devices = [{"key": v["key"], "id": v["id"], "slot": i, "x": dx + _DEVICE_CELLS[i][0],
                "y": dy + _DEVICE_CELLS[i][1], "state": v["state"], "ref": v["ref"]}
               for i, v in enumerate(devs) if v is not None]
    counts = {}
    for x in wmore + dmore:
        counts[x["state"]] = counts.get(x["state"], 0) + 1
    return {"key": d["key"], "session_id": d["sid"], "slot": pod, "x": dx, "y": dy, "w": 2, "h": 2, "name": d["name"],
            "state": d["state"], "seed": _crc(d["sid"] if d["sid"] else d["key"]), "alert": {"stuck": d["stuck"]},
            "ref": d["ref"], "workers": workers, "devices": devices,
            "more": {"n": len(wmore) + len(dmore), "counts": {k: counts[k] for k in _WORKER_STATES if k in counts}}}
