"""Dựng island và các kiểu bóng nổi thật của Wisp (pet_tracker.ui) với dữ liệu mẫu, trên một nền màu, rồi chụp màn
hình. Dùng để so hai nền tảng khi không có máy Mac: workflow mac-probe (nhánh probe/mac-render) chạy trên runner macos-14.

    python tools/ui_shot.py                  # mở, xem bằng mắt, bấm Esc hoặc đợi 60 giây để thoát
    python tools/ui_shot.py --shot out.png   # chụp sau 4 giây rồi thoát (macOS: screencapture, Windows: Pillow)

Không đọc dữ liệu Claude, không mở panel, không ghi state.
"""
from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_tracker import platform as plat  # noqa: E402
from pet_tracker import theme  # noqa: E402
from pet_tracker.config import DEFAULTS, PREF_DEFAULTS  # noqa: E402
from pet_tracker.ui.bubble import Bubble  # noqa: E402
from pet_tracker.ui.island import Island  # noqa: E402
from pet_tracker.ui.kit import Kit  # noqa: E402

BACKDROP = "#5d6f8f"  # nền phía sau: vùng trong suốt phải hiện màu này, không phải đen
X0, Y0 = 40, 60       # góc trên trái vùng mẫu (so với vùng làm việc)


class Stub:
    """Phần của App mà Island / Bubble dùng."""

    def __init__(self, root, kit, prefs: dict, xy=None):
        self.root, self.kit = root, kit
        self.cfg = dict(DEFAULTS)
        self.state = {"x": xy[0], "y": xy[1]} if xy else {}
        self.prefs = dict(PREF_DEFAULTS)
        self.prefs.update(warn_percent=self.cfg.get("warn_percent", 60), danger_percent=self.cfg.get("danger_percent", 85))
        self.prefs.update(prefs)
        self.menus = SimpleNamespace(island_menu=lambda *a: None)
        self.panel = SimpleNamespace(place=lambda: None)

    def toggle_panel(self) -> None:
        pass

    def level_color(self, pct) -> str:
        return theme.level(pct, self.kit.P, self.prefs["warn_percent"], self.prefs["danger_percent"])


class IslandAt(Island):
    """Island đặt ở toạ độ cho trước (bản thật ghim giữa mép trên)."""
    at = (0, 0)

    def _place(self, w: int) -> None:
        self.canvas.configure(width=w, height=self.h)
        self.win.geometry(f"{w}x{self.h}+{self.at[0]}+{self.at[1]}")
        self._clip()


def view(stub, pct, counts, state, upd) -> dict:
    return {"pct": pct, "pct_col": stub.level_color(pct), "counts": counts, "state": state, "update": upd,
            "bars": (pct, 38), "wait_name": "fix-auth-redirect"}


def build(root) -> list:
    l, t, _, _ = plat.work_area(root, None)
    S = plat.dpi_scale(root)

    def kit(name):  # mỗi mẫu một Kit: animator đặt tên theo "island" / "bubble", dùng chung thì chỉ mẫu cuối chạy
        k = Kit(root, S)
        k.set_palette(theme.palette(name))
        return k

    out = []
    row_h = int(200 * S)
    for r, name in enumerate(("dark", "light")):
        y = t + Y0 + r * row_h
        for i, (st, counts, upd) in enumerate((("wait", (1, 1, 0), True), ("run", (0, 2, 1), False))):
            isl = IslandAt(Stub(root, kit(name), {"display": "island"}))
            isl.at = (l + X0 + i * int(300 * S), y)
            isl.update(view(isl.app, 62 if st == "wait" else 34, counts, st, upd))
            isl.show()
            out.append(isl)
        x = l + X0
        y2 = y + int(48 * S)
        for spec in ({"signal": "s01"}, {"signal": "s11"}, {"signal": "s08"},
                     {"bubble_type": "mascot", "mascot": "m01", "chip": 0},
                     {"bubble_type": "mascot", "mascot": "m05", "chip": 1}):
            prefs = {"display": "bubble", "bubble_type": "signal"}
            prefs.update(spec)
            b = Bubble(Stub(root, kit(name), prefs, (x, y2)))
            b.update(view(b.app, 62, (1, 1, 0), "wait" if len(out) % 2 else "done", spec.get("signal") == "s01"))
            b.show()
            out.append(b)
            x += b.box()[0] + int(24 * S)
    return out


def shoot(root, path: str) -> None:
    if plat.IS_MAC:
        subprocess.run(["screencapture", "-x", path], check=True)
    else:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
    try:  # cắt vùng mẫu cho ảnh nhỏ
        from PIL import Image
        im = Image.open(path)
        k = im.width / root.winfo_screenwidth()
        l, t, _, _ = plat.work_area(root, None)
        S = plat.dpi_scale(root)
        im.crop((int(l * k), int(t * k), int((l + X0 + 760 * S) * k), int((t + Y0 + 420 * S) * k))).save(path)
    except Exception as e:
        print("không cắt được ảnh:", e)
    print(f"Tk {root.tk.call('info', 'patchlevel')}, {plat.NAME}, dpi {plat.dpi_scale(root):g} -> {path}")
    root.destroy()


def main() -> None:
    shot = sys.argv[sys.argv.index("--shot") + 1] if "--shot" in sys.argv else None
    root = tk.Tk()
    root.withdraw()
    back = tk.Toplevel(root)
    back.overrideredirect(True)
    back.configure(bg=BACKDROP)
    back.attributes("-topmost", True)  # che các app khác; island / bóng tạo sau nên nằm trên
    back.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    back.bind("<Escape>", lambda e: root.destroy())
    root.update()
    root.wins = build(root)
    back.focus_force()
    if shot:
        root.after(4000, lambda: shoot(root, shot))
    root.after(60_000, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
