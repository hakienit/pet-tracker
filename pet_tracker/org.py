"""Org model: gom session thành cây Project > Team > Session > Worker (hàm thuần, JSON hoá được).

Không import tkinter/os/subprocess, không đọc đĩa. Đầu vào là danh sách session của `ClaudeDataStore.active_sessions`
(đã gắn `git`) với hai khoá `agent_calls` và `workers` theo hợp đồng trong docs/plans/2026-10-22-control-room-plan.md.

    build(sessions, cfg, now) -> {"projects": [Project], "counts": counts}
    Project{name, root, teams[], counts}; Team{top, branch, sessions[], counts}
    Session{...khoá hiện có (trừ agent_calls)..., workers[], counts}
    Worker = Subagent{id, kind, type, department, description, depth, parent, state, started, last_activity, tokens}
           | BgTask{id, kind, tool_use_id, state, started}
    state: subagent running|stuck|done|failed|killed; bgtask running|done|failed|killed|ended
    counts: {"subagent": {...}, "bgtask": {...}}, mỗi nhóm có total/running/stuck/done/failed/killed và "ended"
    ("ended" = mọi worker không còn live, tức không phải running/stuck, nên trùng với done/failed/killed).

Làm sạch: project name/root, team top/branch, mọi trường str của worker, mọi giá trị str ở cấp trên của session
và của dict `git` trong session (bản sao nông, không trả lại dict đầu vào) bị bỏ ký tự điều khiển (C0 \\x00-\\x1f,
\\x7f, C1 \\x80-\\x9f), ký tự bidi U+202A-U+202E và U+2066-U+2069, U+061C, U+200B-U+200F, U+FEFF, dấu ngắt dòng
U+2028/U+2029, rồi cắt 200 ký tự. Giá trị không phải str (số, list như `git["ignored"]`)
được chuyển nguyên, không làm sạch và không sao chép. UI vẫn phải làm sạch lại khi hiển thị.
"""
from __future__ import annotations

import math
import ntpath
import re
from collections import Counter

DEFAULT_PREFIXES = ["les-"]
DEFAULT_STUCK_SEC = 120
MAX_DEPTH = 8
MAX_STR = 200

_CTRL = re.compile("[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028\u2029\u202a-\u202e\u2066-\u2069\u061c\ufeff]")
_LIVE = ("running", "stuck")
_COUNT_KEYS = ("total", "running", "stuck", "done", "failed", "killed", "ended")


# ---------------------------------------------------------------- làm sạch giá trị không tin cậy
def _s(v) -> str:
    # cắt trước rồi mới lọc: chuỗi 1 MB không bị quét hết; đầu ra giống bản lọc-rồi-cắt khi chuỗi <= MAX_STR * 8
    return _CTRL.sub("", v[:MAX_STR * 8])[:MAX_STR] if isinstance(v, str) else ""


def _clean(d: dict, skip=()) -> dict:
    """Bản sao nông của d, giá trị str đi qua _s."""
    return {k: _s(v) if isinstance(v, str) else v for k, v in d.items() if k not in skip}


def _num(v):
    """float hữu hạn hoặc None (bool không tính là số; số lớn hơn float không đổi được thì None)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            f = float(v)
        except OverflowError:
            return None
        if math.isfinite(f):
            return f
    return None


def _int(v, hi=None) -> int:
    try:
        n = max(0, int(v))
    except (TypeError, ValueError, OverflowError):
        return 0
    return n if hi is None else min(n, hi)


def _list_of_str(v) -> list:
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _cfg(cfg):
    """(prefixes, stuck_after_sec); giá trị sai kiểu thì dùng mặc định."""
    cfg = cfg if isinstance(cfg, dict) else {}
    pre = cfg.get("agent_prefixes")
    pre = [p for p in pre if isinstance(p, str) and p] if isinstance(pre, list) else DEFAULT_PREFIXES
    stuck = _num(cfg.get("stuck_after_sec"))
    return pre, stuck if stuck is not None and stuck >= 0 else DEFAULT_STUCK_SEC


# ---------------------------------------------------------------- department
def department(agent_type, prefixes=DEFAULT_PREFIXES) -> str:
    """Phần sau dấu ':' cuối, bỏ một prefix đầu tiên khớp; rỗng thì trả lại agent_type."""
    if not isinstance(agent_type, str):
        return ""
    name = agent_type.rsplit(":", 1)[-1]
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
            break
    return name or agent_type


# ---------------------------------------------------------------- project / team
# Tách đường dẫn bằng ntpath trên mọi hệ điều hành: ntpath coi cả '\' lẫn '/' là dấu phân cách, giữ nguyên kiểu
# dấu của chuỗi gốc, nên đường dẫn Windows ("C:\repo\.git") và POSIX đều chạy đúng, kể cả test trên macOS.
def _trim(p: str) -> str:
    return p.rstrip("\\/") or p


def _repo_root(common: str) -> str:
    p = _trim(common)
    return (ntpath.dirname(p) or p) if ntpath.basename(p) == ".git" else p


def _place(s: dict):
    """(root, team top, branch) của session: git trước, không có git thì cwd."""
    g = s.get("git") if isinstance(s.get("git"), dict) else {}
    cwd, top, common = _s(s.get("cwd")), _s(g.get("top")), _s(g.get("common"))
    team = _trim(top or cwd)
    return (_repo_root(common) if common else team), team, _s(g.get("branch")) or None


# ---------------------------------------------------------------- worker
def _notified(status) -> bool:
    """Chỉ status là chuỗi không rỗng mới là notification; None, "" hay kiểu khác là chưa có."""
    return isinstance(status, str) and status != ""


def _end_state(status) -> str:
    """State của worker đã có notification: failed/killed giữ nguyên, mọi status khác là done."""
    return status if status in ("failed", "killed") else "done"


def _workers(s: dict, prefixes, stuck, now) -> list:
    raw = s.get("workers")
    ws = [w for w in raw if isinstance(w, dict) and w.get("kind") in ("subagent", "bgtask")] \
        if isinstance(raw, list) else []
    subs = [w for w in ws if w["kind"] == "subagent"]

    # ai đã phát ra tool_use Agent/Task nào (None = chính session); chỉ trong phạm vi session này
    owner = {t: None for t in _list_of_str(s.get("agent_calls"))}
    for i, w in enumerate(subs):
        for t in _list_of_str(w.get("agent_calls")):
            owner.setdefault(t, i)
    # chỉ nối parent khi id của nó là chuỗi không rỗng và duy nhất trong session, để `parent` không trỏ nhầm node
    ids = [_s(w.get("id")) for w in subs]
    linkable = {i for i, n in Counter(ids).items() if i and n == 1}
    rp = []
    for w in subs:
        tid = w.get("tool_use_id")
        o = owner.get(tid) if isinstance(tid, str) else None
        rp.append(o if o is not None and _s(subs[o].get("id")) in linkable else None)

    def acyclic(i):
        # tự trỏ, vòng chứa i, hoặc quá MAX_DEPTH tầng thì parent là session; đuôi vòng không chứa i thì giữ
        seen, cur, n = {i}, rp[i], 0
        while cur is not None:
            if cur == i or n >= MAX_DEPTH - 1:
                return False
            if cur in seen:
                break
            seen.add(cur)
            cur, n = rp[cur], n + 1
        return True

    parent = [rp[i] if acyclic(i) else None for i in range(len(subs))]
    kids = [[] for _ in subs]
    for i, p in enumerate(parent):
        if p is not None:
            kids[p].append(i)

    memo = {}

    def state(i):
        if i not in memo:
            w = subs[i]
            ns = w.get("notif_status")
            if w.get("finished") is True or _notified(ns):
                memo[i] = _end_state(ns)
            else:
                last = next((x for x in map(_num, (w.get("mtime"), w.get("last_activity"), w.get("started")))
                             if x is not None), None)
                live = (last is not None and now - last <= stuck) or _int(w.get("open_tools")) > 0 \
                    or any(state(c) == "running" for c in kids[i])
                memo[i] = "running" if live else "stuck"
        return memo[i]

    started_at = _num(s.get("started_at"))
    out, j = [], 0
    for w in ws:
        if w["kind"] == "subagent":
            t = _s(w.get("agent_type"))
            p = parent[j]
            out.append({
                "id": _s(w.get("id")), "kind": "subagent", "type": t, "department": department(t, prefixes),
                "description": _s(w.get("description")), "depth": _int(w.get("depth"), MAX_DEPTH),
                "parent": None if p is None else _s(subs[p].get("id")), "state": state(j),
                "started": _num(w.get("started")), "last_activity": _num(w.get("last_activity")),
                "tokens": _int(w.get("tokens")),
            })
            j += 1
        else:
            started, status = _num(w.get("started")), w.get("status")
            if _notified(status):
                st = _end_state(status)
            elif started is not None and started_at is not None and started < started_at:
                st = "ended"    # task của lần chạy trước khi resume: notification không còn nên không thể running
            else:
                st = "running"
            out.append({"id": _s(w.get("id")), "kind": "bgtask", "tool_use_id": _s(w.get("tool_use_id")),
                        "state": st, "started": started})
    return out


# ---------------------------------------------------------------- counts
def _zero() -> dict:
    return {k: dict.fromkeys(_COUNT_KEYS, 0) for k in ("subagent", "bgtask")}


def _tally(counts: dict, workers: list):
    for w in workers:
        d, st = counts[w["kind"]], w["state"]
        d["total"] += 1
        if st != "ended":
            d[st] += 1
        if st not in _LIVE:
            d["ended"] += 1


def _add(into: dict, other: dict):
    for k, d in other.items():
        for key, n in d.items():
            into[k][key] += n


# ---------------------------------------------------------------- build
def build(sessions, cfg, now) -> dict:
    prefixes, stuck = _cfg(cfg)
    projects, total = {}, _zero()
    for s in sessions if isinstance(sessions, list) else []:
        if not isinstance(s, dict):
            continue
        root, top, branch = _place(s)
        proj = projects.get(root)
        if proj is None:
            proj = projects[root] = {"name": ntpath.basename(root) or root or "(unknown)", "root": root,
                                     "teams": {}, "counts": _zero()}
        team = proj["teams"].get(top)
        if team is None:
            team = proj["teams"][top] = {"top": top, "branch": branch, "sessions": [], "counts": _zero()}
        elif team["branch"] is None:
            team["branch"] = branch
        ws = _workers(s, prefixes, stuck, now)
        sc = _zero()
        _tally(sc, ws)
        item = _clean(s, skip=("agent_calls", "workers"))
        if isinstance(item.get("git"), dict):
            item["git"] = _clean(item["git"])
        item["workers"], item["counts"] = ws, sc
        team["sessions"].append(item)
        for c in (team["counts"], proj["counts"], total):
            _add(c, sc)
    out = []
    for p in projects.values():
        p["teams"] = list(p["teams"].values())
        out.append(p)
    return {"projects": out, "counts": total}
