"""Thử trên Mac thật: cách vẽ nào hiện được trong cửa sổ trong suốt / bo góc của Tk, để chọn cách vẽ bóng và island.

    python3 tools/mac_probe.py

Mở 8 ô nổi ở góc trên trái màn hình, mỗi ô đánh số. Ô đạt = thấy đĩa XANH LÁ mép mịn trên nền trong suốt (ô 5-8 nền
xám đậm) cùng số của ô. Ghi lại số ô thấy đĩa, thấy ô đen / ô trống, rồi bấm vào ô bất kỳ hoặc Esc để thoát
(tự thoát sau 90 giây). Lần cập nhật lại ảnh sau 1 giây kiểm lỗi "chỉ vẽ ở lần đầu / chỉ vẽ sau khi đổi ảnh".

    python3 tools/mac_probe.py --shot probe.png   # CI (.github/workflows/mac-probe.yml): chụp màn hình, tự chấm

--shot: sau 3 giây chụp bằng `screencapture`, đọc màu một điểm trong đĩa của mỗi ô (cần Pillow) và in bảng
PASS / BLACK / EMPTY dạng markdown, rồi thoát.
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_tracker import platform as plat  # noqa: E402
from pet_tracker import render  # noqa: E402
from pet_tracker.ui import gfx  # noqa: E402

D = 96          # cỡ ô
GREEN = "#2ea043"
SOLID = "#26262c"  # nền đặc cho ô 5-8

CASES = [
    # (số, cửa sổ, cách vẽ, mô tả)
    (1, "transparent", "png", "-transparent + Canvas + PhotoImage PNG alpha (cách 0.2 đang dùng)"),
    (2, "transparent", "put", "-transparent + Canvas + PhotoImage put() (pixel đặc, nền key xám)"),
    (3, "transparent", "poly", "-transparent + Canvas oval/polygon (cách 0.1.8, đối chứng)"),
    (4, "transparent", "label", "-transparent + Label image PNG alpha"),
    (5, "rounded", "png", "đặc + round_corners (layer bo góc) + PNG alpha trên nền đặc"),
    (6, "rounded", "put", "đặc + round_corners + put() (cách panel 0.2 trên Mac sau merge)"),
    (7, "plain", "png", "cửa sổ đặc thường + PNG alpha (đối chứng)"),
    (8, "rounded", "png-r", "đặc + round_corners bo tròn hết cỡ (đĩa) + PNG alpha: thay cho cửa sổ trong suốt?"),
    (9, "transparent-solid", "png", "-transparent + Canvas nền ĐẶC + PNG alpha: lỗi do nền systemTransparent?"),
]


def disc_rows():
    return gfx.shape_rows(D - 16, D - 16, (D - 16) / 2, GREEN, "#ffffff", 1.5)


def png_photo(master):
    return tk.PhotoImage(master=master, data=base64.b64encode(render.png_bytes(disc_rows())).decode("ascii"),
                         format="png")


def put_photo(master, bg):
    rows = disc_rows()
    img = tk.PhotoImage(master=master, width=len(rows[0]), height=len(rows))
    img.put(render.to_photo_data(gfx._flatten(rows, bg)))
    return img


def build(root, n, kind, how, x, y):
    w = tk.Toplevel(root)
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    bg = SOLID
    if kind.startswith("transparent"):
        plat.make_transparent(w)
        if kind == "transparent":
            bg = "systemTransparent" if plat.IS_MAC else plat.transparent_key()
    w.geometry(f"{D}x{D}+{x}+{y}")
    imgs = []
    if how == "label":
        img = png_photo(w)
        imgs.append(img)
        lb = tk.Label(w, image=img, bg=bg, bd=0)
        lb.pack(fill="both", expand=True)
        widget, redo = lb, lambda: lb.configure(image=img)
    else:
        c = tk.Canvas(w, width=D, height=D, bg=bg, highlightthickness=0, bd=0)
        c.pack()
        widget = c
        if how == "poly":
            c.create_oval(8, 8, D - 8, D - 8, fill=GREEN, outline="#ffffff", width=1.5)
            redo = lambda: None  # noqa: E731
        else:
            img = put_photo(w, "#808080" if kind == "transparent" else SOLID) if how == "put" else png_photo(w)
            imgs.append(img)
            it = c.create_image(8, 8, anchor="nw", image=img)
            redo = lambda: c.itemconfigure(it, image=img)  # noqa: E731
        c.create_text(D / 2, D / 2, text=str(n), fill="#ffffff", font=("Helvetica", 22, "bold"))
    w._imgs = imgs
    if kind == "rounded":
        w.update_idletasks()
        mac = sys.modules.get("pet_tracker.platform.mac")
        old = mac.CORNER_RADIUS if mac else None
        if mac and how == "png-r":
            mac.CORNER_RADIUS = D / 2  # round_corners đọc hằng này lúc gọi
        ok = plat.round_corners(w, "#ffffff")
        if mac:
            mac.CORNER_RADIUS = old
        print(f"  ô {n}: round_corners -> {ok}")
    widget.bind("<Button-1>", lambda e: root.destroy())
    w.bind("<Escape>", lambda e: root.destroy())
    root.after(1000, redo)
    return w


def classify(rgb) -> str:
    r, g, b = rgb[:3]
    if g > 110 and r < 110 and b < 130:
        return "PASS"
    if max(r, g, b) < 24:
        return "BLACK"
    return "EMPTY"


def shoot(root, path, cells):
    """Chụp màn hình, chấm từng ô theo màu điểm (x + 22, y + D/2): nằm trong đĩa, bên trái số."""
    subprocess.run(["screencapture", "-x", path], check=True)
    from PIL import Image
    im = Image.open(path).convert("RGB")
    k = im.width / root.winfo_screenwidth()  # Retina: ảnh 2x so với point của Tk
    hexc = lambda c: "#%02x%02x%02x" % c  # noqa: E731
    desk = im.getpixel((int(im.width * 0.6), int(im.height * 0.6)))  # nền desktop: đen thì BLACK = không vẽ gì
    print(f"\nTk {root.tk.call('info', 'patchlevel')}, ảnh {im.width}x{im.height}, tỉ lệ {k:g}, desktop {hexc(desk)}\n")
    print("| ô | kết quả | màu trong đĩa | màu góc ảnh (ngoài đĩa) | cách vẽ |\n|---|---|---|---|---|")
    desc = {n: d for n, _, _, d in CASES}
    for n, x, y in cells:
        rgb = im.getpixel((int((x + 22) * k), int((y + D / 2) * k)))
        corner = im.getpixel((int((x + 10) * k), int((y + 10) * k)))  # trong khung ảnh, ngoài đĩa: Tk 9 vẽ đen?
        print(f"| {n} | {classify(rgb)} | {hexc(rgb)} | {hexc(corner)} | {desc[n]} |")
    root.destroy()


def main():
    shot = sys.argv[sys.argv.index("--shot") + 1] if "--shot" in sys.argv else None
    root = tk.Tk()
    root.withdraw()
    print(f"Tk {root.tk.call('info', 'patchlevel')}, windowingsystem={root.tk.call('tk', 'windowingsystem')}, "
          f"Python {sys.version.split()[0]}")
    for n, _, _, desc in CASES:
        print(f"  {n}. {desc}")
    l, t, _, _ = plat.work_area(root, None)
    wins, cells = [], []
    for i, (n, kind, how, _) in enumerate(CASES):
        x = l + 20 + (i % 4) * (D + 20)
        y = t + 20 + (i // 4) * (D + 40)
        cells.append((n, x, y))
        try:
            wins.append(build(root, n, kind, how, x, y))
        except Exception as e:
            print(f"  ô {n}: LỖI {type(e).__name__}: {e}")
    if wins:
        wins[0].focus_force()
    if shot:
        root.after(3000, lambda: shoot(root, shot, cells))
    root.after(90_000, root.destroy)
    print("Ghi lại ô nào thấy đĩa xanh lá; bấm vào ô bất kỳ hoặc Esc để thoát.")
    root.mainloop()


if __name__ == "__main__":
    main()
