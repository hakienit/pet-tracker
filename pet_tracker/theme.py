"""Token giao diện dùng chung cho Windows và macOS: màu (tối / sáng), cỡ chữ (pixel), chuyển động.

Nguồn: docs/site/assets/wisp-ui.js (spec final). Đổi màu ở đây thì sửa cả bên đó để landing khớp app.
"""
from __future__ import annotations

DARK = {
    "name": "dark",
    "bg": "#111215", "surf": "#1a1b20", "line": "#2a2c33", "fg": "#f2f2f4", "fg2": "#cfd1d8", "mut": "#9c9fa9",
    "track": "#2a2c33", "wait": "#ffb02e", "run": "#58a6ff", "done": "#3fd0a4", "idle": "#8b8e98",
    "ok": "#3fd0a4", "warn": "#ffb02e", "danger": "#ff6166", "upd": "#58a6ff",
    "waitBg": "#2a2112", "runBg": "#15202e", "doneBg": "#13241f", "idleBg": "#1a1b20",
    "code": "#141210", "codeFg": "#ffd79a",
    "isl": "#08080a", "islFg": "#f2f2f4", "islSep": "#2e3038", "dim": "#4a4c55",
    "disc": "#16171b", "discBd": "#3a3b45", "btnFg": "#1a1205", "on": "#3fd0a4", "off": "#3a3c44",
    "seg": "#22242a", "segOn": "#33363e", "menuBg": "#1b1c22", "hover": "#272830", "dangerBg": "#3a2326",
    "fringe": "#0d0d11",
    # viền động theo trạng thái: (c1, c2, c3, chu kỳ giây)
    "ab": {"wait": ("#ffb02e", "#ff6a1a", "#e8432f", 1.8), "run": ("#58a6ff", "#b9dbff", "#2f6fd6", 2.6),
           "done": ("#3fd0a4", "#b4f2df", "#1f9e7a", 4.5), "idle": ("#4f525b", "#a3a6af", "#4f525b", 6.0),
           "quota": ("#ff6166", "#ffc2c4", "#c62828", 2.2), "update": ("#58a6ff", "#b9dbff", "#2f6fd6", 3.0)},
}
LIGHT = {
    "name": "light",
    "bg": "#f6f6f8", "surf": "#ffffff", "line": "#e2e4e9", "fg": "#16171b", "fg2": "#383b44", "mut": "#5b5f6a",
    "track": "#e6e7eb", "wait": "#a85600", "run": "#1f5fd6", "done": "#0b7a5a", "idle": "#6b6e78",
    "ok": "#0b7a5a", "warn": "#a85600", "danger": "#c62828", "upd": "#1f5fd6",
    "waitBg": "#fff3dc", "runBg": "#eaf1ff", "doneBg": "#e6f6f0", "idleBg": "#ffffff",
    "code": "#fbf3e6", "codeFg": "#7a3e00",
    "isl": "#ffffff", "islFg": "#16171b", "islSep": "#e2e4e9", "dim": "#c3c6cd",
    "disc": "#ffffff", "discBd": "#d5d8de", "btnFg": "#ffffff", "on": "#0b7a5a", "off": "#c9ccd3",
    "seg": "#eceef2", "segOn": "#ffffff", "menuBg": "#ffffff", "hover": "#f0f1f4", "dangerBg": "#fde8e8",
    "fringe": "#c9ccd3",
    "ab": {"wait": ("#e08a00", "#ff6a1a", "#c2410c", 1.8), "run": ("#1f5fd6", "#8fb8ff", "#123f99", 2.6),
           "done": ("#0b7a5a", "#7fd8b8", "#065c43", 4.5), "idle": ("#b7bac2", "#6b6e78", "#b7bac2", 6.0),
           "quota": ("#c62828", "#ff9a9a", "#8e1b1b", 2.2), "update": ("#1f5fd6", "#8fb8ff", "#123f99", 3.0)},
}

# cỡ chữ theo pixel (Tk: size âm = pixel) để hai hệ điều hành cùng kích thước
TYPE = {"meta": 12, "body": 13, "title": 14, "head": 15, "num": 18, "big": 19}
# chuyển động (ms)
MOTION = {"enter": 180, "exit": 120, "resize": 200, "frame": 40}


def palette(name: str) -> dict:
    return LIGHT if name == "light" else DARK


def level(pct, P: dict, warn: float, danger: float) -> str:
    """Màu theo mức dùng: ok / warn / danger."""
    if pct is None:
        return P["mut"]
    return P["danger"] if pct >= danger else P["warn"] if pct >= warn else P["ok"]


def _lum(hex_: str) -> float:
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
