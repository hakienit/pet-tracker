"""Mascot: thân (assets/mascots.json, xuất từ docs/site/assets/wisp-ui.js) + mặt theo biểu cảm, vẽ bằng vector.py.

Biểu cảm (mood): idle (mắt nhắm + z), run (mắt mở), wait (mắt to + "!"), done (mắt cười), quota (lo + mồ hôi).
Ảnh đã vẽ được cache theo (id, mood, cỡ, màu, theme, dáng) trong RAM và dưới dạng PNG trong <state>/mascots/
để lần mở sau không phải vẽ lại.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import render, vector
from .assets import asset_path

MOODS = ("idle", "run", "wait", "done", "quota")
BOX = 64.0          # khung toạ độ của hình
PAD = 0.14          # lề quanh khung (chữ z, dấu ! và giọt mồ hôi vẽ lấn ra ngoài 64x64)


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads(asset_path("mascots.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"hues": [0], "mascots": []}


def all_mascots() -> list:
    return _data()["mascots"]


def hues() -> list:
    return _data()["hues"]


def get(mid: str) -> dict:
    ms = all_mascots()
    return next((m for m in ms if m["id"] == mid), ms[0] if ms else None)


def face_svg(m: dict, mood: str, P: dict) -> str:
    """Giống face() trong wisp-ui.js. P: palette (theme.DARK / LIGHT)."""
    x, y, dx, r = m["face"]
    e = m.get("eye") or "#2a1714"
    L2, R2 = x - dx, x + dx
    s = []

    def eye_open(cx, rr):
        if m.get("sq"):
            return f'<rect x="{cx - rr}" y="{y - rr}" width="{rr * 2}" height="{rr * 2}" rx="1" fill="{e}"/>'
        return (f'<circle cx="{cx}" cy="{y}" r="{rr}" fill="{e}"/>'
                f'<circle cx="{cx + rr * 0.35}" cy="{y - rr * 0.4}" r="{rr * 0.32}" fill="#ffffff" opacity=".9"/>')

    if mood == "idle":
        for c in (L2, R2):
            s.append(f'<path d="M{c - r} {y} q{r} {r * 0.9} {r * 2} 0" stroke="{e}" stroke-width="{r * 0.7}" '
                     f'fill="none" stroke-linecap="round"/>')
        z = P["idle"]  # hai chữ z (vẽ bằng nét, Tk không có font trong ảnh)
        s.append(f'<path d="M52 10h5l-5 6h5" stroke="{z}" stroke-width="1.6" fill="none" stroke-linecap="round"/>')
        s.append(f'<path d="M57.5 3h3.5l-3.5 4h3.5" stroke="{z}" stroke-width="1.3" fill="none" stroke-linecap="round"/>')
    elif mood == "run":
        s += [eye_open(L2, r), eye_open(R2, r),
              f'<path d="M{x - 2.5} {y + r * 2.4}h5" stroke="{e}" stroke-width="1.6" stroke-linecap="round" fill="none"/>']
    elif mood == "wait":
        for c in (L2, R2):
            s.append(f'<circle cx="{c}" cy="{y}" r="{r * 1.45}" fill="#ffffff"/><circle cx="{c}" cy="{y}" r="{r * 0.8}" fill="{e}"/>')
        mark = "#ffffff" if P["name"] == "light" else "#1a1205"
        s.append(f'<circle cx="{x}" cy="{y + r * 2.7}" r="{r * 0.6}" fill="{e}"/><circle cx="54" cy="10" r="8" fill="{P["wait"]}"/>'
                 f'<path d="M54 6v5" stroke="{mark}" stroke-width="2.4" stroke-linecap="round" fill="none"/>'
                 f'<circle cx="54" cy="13.9" r="1.3" fill="{mark}"/>')
    elif mood == "quota":
        s += [eye_open(L2, r * 0.9), eye_open(R2, r * 0.9)]
        s.append(f'<path d="M{L2 - r * 1.3} {y - r * 2.3}l{r * 2} {r * 0.9}M{R2 + r * 1.3} {y - r * 2.3}l{-r * 2} {r * 0.9}" '
                 f'stroke="{e}" stroke-width="1.5" stroke-linecap="round" fill="none"/>')
        s.append(f'<path d="M{x - 4} {y + r * 3}q4 {-r * 1.4} 8 0" stroke="{e}" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
                 '<path d="M53 14c3 4 4 6 4 8a4 4 0 0 1-8 0c0-2 1-4 4-8z" fill="#7cc4ff"/>')
    else:  # done
        for c in (L2, R2):
            s.append(f'<path d="M{c - r} {y + r * 0.4} q{r} {-r * 1.6} {r * 2} 0" stroke="{e}" stroke-width="{r * 0.7}" '
                     f'fill="none" stroke-linecap="round"/>')
        s.append(f'<path d="M{x - 4} {y + r * 1.8} q4 {r * 1.6} 8 0" stroke="{e}" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
                 f'<path d="M9 12l1.5 3 3 1.5-3 1.5L9 21l-1.5-3-3-1.5 3-1.5z" fill="{P["done"]}"/>')
    if m.get("fang") and mood != "idle":
        s.append(f'<path d="M{x + 1} {y + r * 2.6}l1.5 2.5 1.5-2.5z" fill="#ffffff"/>')
    return "".join(s)


@lru_cache(maxsize=256)
def _shapes(mid: str, mood: str, theme: str, hue: float) -> list:
    from .theme import palette
    m = get(mid)
    if m is None:
        return []
    return vector.parse(m["body"], hue) + vector.parse(face_svg(m, mood, palette(theme)))


def canvas_size(size: int) -> int:
    """Cạnh ảnh (pixel) cho mascot cỡ size: có lề PAD mỗi bên."""
    return int(round(size * (1 + 2 * PAD)))


def rows(mid: str, mood: str, size: int, theme: str = "dark", hue: float = 0.0, sx: float = 1.0, sy: float = 1.0,
         rot: float = 0.0) -> list:
    """Ảnh RGBA (list hàng) cạnh canvas_size(size). sx / sy / rot: dáng (co giãn, xoay) quanh đáy giữa hình."""
    n = canvas_size(size)
    k = size / BOX
    pad = (n - size) / 2
    m = vector.affine(scale=k, sx=sx, sy=sy, rot=rot, origin=(32.0, 60.0), tx=pad, ty=pad)
    return vector.rasterize(_shapes(mid, mood, theme, hue), n, n, m)


def png(mid: str, mood: str, size: int, theme: str, hue: float, cache_dir: Path | None = None, **pose) -> bytes:
    """PNG của rows(), cache trên đĩa nếu có cache_dir."""
    key = f"{mid}-{mood}-{size}-{theme}-{int(hue)}-" + "-".join(f"{k}{pose[k]:g}" for k in sorted(pose)) + ".png"
    if cache_dir is not None:
        f = Path(cache_dir) / key
        try:
            return f.read_bytes()
        except OSError:
            pass
    data = render.png_bytes(rows(mid, mood, size, theme, hue, **pose))
    if cache_dir is not None:
        try:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            (Path(cache_dir) / key).write_bytes(data)
        except OSError:
            pass
    return data
