"""Biến landing thành README hiển thị được trên GitHub.

GitHub README không chạy JS / CSS, nên mỗi khối của landing được chụp thành ảnh (nền trong suốt, góc bo, 2x),
phần demo chạy được ghép thành ảnh động APNG (GitHub hiển thị như PNG thường). Chữ quan trọng (tiêu đề, lệnh cài,
cách dùng, riêng tư) để ở dạng markdown: đọc được, tìm được, và code block có sẵn nút copy của GitHub.

    python tools/shoot_landing.py                  # landing chính (docs/site/index.html), en + vi
    python tools/shoot_landing.py a-aurora         # một mẫu lưu trong docs/site/landing/
    python tools/shoot_landing.py --all            # landing chính và mọi mẫu
    python tools/shoot_landing.py --preview        # thêm preview-*.html render bằng API markdown của GitHub

Ra: landing chính -> docs/site/{README.md, README.vi.md, img/*.png};
    mẫu -> docs/site/landing/readme/<mẫu>/ (không commit, chạy lại khi cần).
Cần Chrome hoặc Edge, và mạng (font Archivo từ Google Fonts; --preview gọi api.github.com).
"""
from __future__ import annotations

import html
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "site"
LANDING = SITE / "landing"
OUT = LANDING / "readme"
WIDTH = 1000   # bề rộng khối khi chụp (CSS px), khớp .shot-on trong landing-copy.js; README hiện ảnh rộng 880 nên chữ gần đúng cỡ thật
DPR = 2        # ảnh rộng 2000 px: nét trên màn hình retina
REPO = "https://github.com/hakienit/pet-tracker"
WIN_CMD = "irm https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.ps1 | iex"
MAC_CMD = "curl -fsSL https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.sh | bash"

# trang -> (file html, thư mục ra, các khối ảnh tĩnh, trạng thái của ảnh động demo hoặc None)
PAGES = {
    "main": (SITE / "index.html", SITE, ["hero", "features", "custom", "mascots"], ["idle", "run", "wait", "done"]),
    "a-aurora": (LANDING / "a-aurora.html", OUT / "a-aurora", ["hero", "features", "custom", "mascots"], ["idle", "run", "wait", "done"]),
    "c-bento": (LANDING / "c-bento.html", OUT / "c-bento", ["hero", "features", "custom"], None),
    "e-parade": (LANDING / "e-parade.html", OUT / "e-parade", ["hero", "features", "mascots", "custom"], ["idle", "run", "wait", "done", "quota"]),
}

TEXT = {
    "en": {
        "tag": "Know the moment your Claude Code agents need you.",
        "sub": "Wisp floats at the top of your screen: quota with a forecast, every running session, and a gentle nudge when one is waiting for you.",
        "win": "Download for Windows", "mac": "macOS (beta)", "other": "Tiếng Việt", "other_file": "README.vi.md",
        "install": "Install in one line", "install_l": "Downloads the latest release, checks its SHA256 and starts Wisp. Run it again to update. Requires Claude Code, signed in.",
        "win_h": "Windows 10/11, in PowerShell:", "mac_h": "macOS (beta), in Terminal:", "manual": "Manual download",
        "demo": "Idle, running, needs you, done: the island follows your sessions.",
        "privacy": "Private by design", "privacy_l": "Wisp reads Claude Code data on your machine only (`~/.claude`). Your login token goes only to `api.anthropic.com` for quota; turn it off with `\"quota_api_enabled\": false`. Hooks post to `127.0.0.1` only.",
        "more": "Learn more", "guide": "Full guide", "changelog": "Changelog", "site": "Website",
        "foot": "Wisp is a personal project, not an Anthropic product. Quota uses the unofficial endpoint behind Claude Code's `/usage` and may change at any time.",
        "spec": "Design spec",
        "alt": {"features": "Everything at a glance: needs you, quota forecast, every session, one click back, clean up, make it yours",
                "custom": "Pick your bubble: signal ring styles or a mascot", "mascots": "40 mascots, five moods"},
        "use": "Use", "use_t": [("Action", "Result"),
                                ("Click the island or bubble", "open / close the panel"),
                                ("Right-click the island or bubble", "refresh, settings, switch island / bubble, mute 1 hour, check for updates, quit"),
                                ("Click a session", "bring its window to the front"),
                                ("Right-click a session, or ⋯", "open folder, copy ID, details, mute, handoff, close, delete"),
                                ("Click a lane title", "collapse / expand that lane")],
    },
    "vi": {
        "tag": "Biết ngay lúc agent Claude Code cần bạn.",
        "sub": "Wisp nổi ở mép trên màn hình: quota có dự báo, mọi session đang chạy, và nhắc nhẹ khi có session đang chờ bạn.",
        "win": "Tải cho Windows", "mac": "macOS (thử nghiệm)", "other": "English", "other_file": "README.md",
        "install": "Cài bằng một dòng", "install_l": "Tải bản mới nhất, kiểm SHA256 rồi mở Wisp. Chạy lại để cập nhật. Cần Claude Code đã đăng nhập.",
        "win_h": "Windows 10/11, dán vào PowerShell:", "mac_h": "macOS (thử nghiệm), dán vào Terminal:", "manual": "Tải tay",
        "demo": "Rảnh, đang chạy, cần bạn, xong: island đổi theo session của bạn.",
        "privacy": "Riêng tư từ đầu", "privacy_l": "Wisp chỉ đọc dữ liệu Claude Code trên máy bạn (`~/.claude`). Token chỉ gửi tới `api.anthropic.com` để lấy quota; tắt bằng `\"quota_api_enabled\": false`. Hooks chỉ gửi tới `127.0.0.1`.",
        "more": "Tìm hiểu thêm", "guide": "Hướng dẫn đầy đủ", "changelog": "Lịch sử thay đổi", "site": "Website",
        "foot": "Wisp là dự án cá nhân, không phải sản phẩm của Anthropic. Quota dùng endpoint không chính thức của lệnh `/usage` trong Claude Code, có thể đổi bất kỳ lúc nào.",
        "spec": "Spec thiết kế",
        "alt": {"features": "Mọi thứ trong một cái nhìn: cần bạn, dự báo quota, mọi session, một click về cửa sổ, dọn dẹp, tuỳ biến",
                "custom": "Chọn bóng nổi: các kiểu vòng tín hiệu hoặc mascot", "mascots": "40 mascot, năm biểu cảm"},
        "use": "Dùng", "use_t": [("Thao tác", "Kết quả"),
                                 ("Click vào island hoặc bóng", "mở / đóng panel"),
                                 ("Click phải vào island hoặc bóng", "làm mới, cài đặt, đổi island / bóng, tắt âm thanh 1 giờ, kiểm tra cập nhật, thoát"),
                                 ("Click vào session", "đưa cửa sổ của session lên trước"),
                                 ("Click phải vào session, hoặc ⋯", "mở thư mục, sao chép ID, chi tiết, tắt thông báo, handoff, đóng, xoá"),
                                 ("Click vào tên làn", "thu / mở làn đó")],
    },
}


# ---------------------------------------------------------------- trình duyệt
def find_browser() -> str:
    for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium"):
        if Path(c).exists():
            return c
    sys.exit("Không tìm thấy Chrome / Edge")


class Shooter:
    def __init__(self):
        self.browser = find_browser()
        self.prof = tempfile.TemporaryDirectory()

    def _run(self, extra, url, timeout=120):
        args = [self.browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={self.prof.name}",
                "--run-all-compositor-stages-before-draw", "--default-background-color=00000000"] + extra + [url]
        return subprocess.run(args, capture_output=True, timeout=timeout)

    def height(self, url: str) -> int:
        r = self._run([f"--window-size={WIDTH},1200", "--virtual-time-budget=5000", "--dump-dom"], url)
        m = re.search(rb"<title>H=(\d+)</title>", r.stdout)
        if not m:
            raise RuntimeError(f"không đo được chiều cao: {url}")
        return int(m.group(1)) + 2

    def shot(self, url: str, out: Path) -> None:
        h = self.height(url)
        out.parent.mkdir(parents=True, exist_ok=True)
        self._run([f"--window-size={WIDTH},{h}", f"--force-device-scale-factor={DPR}", "--virtual-time-budget=5000",
                   f"--screenshot={out}"], url)
        if not out.exists():
            raise RuntimeError(f"chụp lỗi: {url}")
        recompress(out)


# ---------------------------------------------------------------- APNG (không cần thư viện ngoài)
def _chunks(data: bytes):
    pos = 8
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        yield data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n


def _chunk(tag: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)


def recompress(path: Path) -> None:
    """Nén lại IDAT của Chrome ở mức zlib 9 (không mất dữ liệu), gộp thành một IDAT, bỏ chunk phụ."""
    chunks = list(_chunks(path.read_bytes()))
    raw = zlib.decompress(b"".join(b for t, b in chunks if t == b"IDAT"))
    keep = [_chunk(t, b) for t, b in chunks if t in (b"IHDR", b"PLTE", b"tRNS")]
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(keep) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


def apng(frames: list, out: Path, delay_ms: int = 1600) -> None:
    """Ghép các PNG cùng kích thước thành APNG lặp vô hạn. Khung đầu dùng IDAT (trình xem không hỗ trợ APNG thấy khung này)."""
    parsed = [list(_chunks(f.read_bytes())) for f in frames]
    ihdr = next(b for t, b in parsed[0] if t == b"IHDR")
    w, h = struct.unpack(">II", ihdr[:8])
    for p in parsed[1:]:
        if next(b for t, b in p if t == b"IHDR") != ihdr:
            raise RuntimeError("các khung không cùng kích thước / định dạng")
    seq = 0
    parts = [b"\x89PNG\r\n\x1a\n", _chunk(b"IHDR", ihdr), _chunk(b"acTL", struct.pack(">II", len(frames), 0))]
    for i, p in enumerate(parsed):
        parts.append(_chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0, delay_ms, 1000, 0, 0)))
        seq += 1
        for t, b in p:
            if t != b"IDAT":
                continue
            if i == 0:
                parts.append(_chunk(b"IDAT", b))
            else:
                parts.append(_chunk(b"fdAT", struct.pack(">I", seq) + b))
                seq += 1
    parts.append(_chunk(b"IEND", b""))
    out.write_bytes(b"".join(parts))


# ---------------------------------------------------------------- README
def readme(page: Path, out: Path, secs: list, lang: str, demo: bool) -> str:
    T = TEXT[lang]
    sfx = f"-{lang}.png"
    img = lambda name, alt, w=880: f'<p align="center"><img src="img/{name}{sfx}" width="{w}" alt="{html.escape(alt)}"></p>'  # noqa: E731
    rel = lambda p: Path(os.path.relpath(p, out)).as_posix()  # noqa: E731
    lines = [
        f'<!-- Tạo bởi tools/shoot_landing.py từ {page.relative_to(ROOT).as_posix()}; sửa landing rồi chạy lại script, đừng sửa tay. -->',
        img("hero", T["tag"]),
        "",
        f'<p align="center"><b>{html.escape(T["sub"])}</b></p>',
        "",
        f'<p align="center"><a href="{REPO}/releases/latest/download/wisp-win-x64.zip"><b>{T["win"]}</b></a> · '
        f'<a href="{REPO}/releases/latest/download/wisp-macos-universal2.dmg">{T["mac"]}</a> · '
        f'<a href="{REPO}/releases">Releases</a> · <a href="{T["other_file"]}">{T["other"]}</a></p>',
        "",
        f'<p align="center"><img src="https://img.shields.io/github/v/release/hakienit/pet-tracker?label=release" alt="release"> '
        '<img src="https://img.shields.io/badge/Windows%2010%2F11-ok-3fb950" alt="Windows"> '
        '<img src="https://img.shields.io/badge/macOS-beta-e3b341" alt="macOS beta"></p>',
        "",
    ]
    if demo:
        lines += [img("demo", T["demo"], 760), f'<p align="center"><sub>{html.escape(T["demo"])}</sub></p>', ""]
    lines += [f"## {T['install']}", "", T["install_l"], "", T["win_h"], "", "```powershell", WIN_CMD, "```", "",
              T["mac_h"], "", "```bash", MAC_CMD, "```", "",
              f"{T['manual']}: [wisp-win-x64.zip]({REPO}/releases/latest/download/wisp-win-x64.zip) · "
              f"[wisp-macos-universal2.dmg]({REPO}/releases/latest/download/wisp-macos-universal2.dmg)", ""]
    for s in secs:
        if s != "hero":
            lines += [img(s, T["alt"][s]), ""]
    head, *rows = T["use_t"]
    lines += [f"## {T['use']}", "", f"| {head[0]} | {head[1]} |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows] + [""]
    lines += [f"## {T['privacy']}", "", T["privacy_l"], "", f"## {T['more']}", "",
              f"- [{T['guide']}]({rel(ROOT / 'docs' / 'GUIDE.md')}) · [{T['changelog']}]({rel(ROOT / 'CHANGELOG.md')}) · "
              f"[{T['site']}](https://hakienit.github.io/pet-tracker/site/) · [{T['spec']}](https://hakienit.github.io/pet-tracker/site/design.html)",
              "", f"<sub>{T['foot']}</sub>", ""]
    return "\n".join(lines)


def preview(md_path: Path, lang: str, dest: Path) -> None:
    """Render README bằng API markdown của GitHub (gfm, đúng như trên repo) + CSS của GitHub, sáng và tối.
    Ghi vào dest (không commit); <base> trỏ về thư mục README để ảnh img/ vẫn hiện."""
    body = json.dumps({"text": md_path.read_text(encoding="utf-8"), "mode": "gfm", "context": "hakienit/pet-tracker"}).encode()
    req = urllib.request.Request("https://api.github.com/markdown", data=body,
                                 headers={"Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    rendered = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    for theme in ("dark", "light"):
        css = f"https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-{theme}.min.css"
        bg = "#0d1117" if theme == "dark" else "#ffffff"
        page = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>README preview ({theme})</title><base href="{md_path.parent.as_uri()}/"><link rel="stylesheet" href="{css}">'
                f'<style>body{{margin:0;background:{bg}}}.markdown-body{{box-sizing:border-box;max-width:1012px;margin:0 auto;padding:32px 45px;'
                f'border:1px solid {"#30363d" if theme == "dark" else "#d0d7de"};border-radius:6px;margin-top:24px;margin-bottom:24px}}</style></head>'
                f'<body><article class="markdown-body">{rendered}</article></body></html>')
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"preview-{lang}-{theme}.html").write_text(page, encoding="utf-8")


def main(argv: list) -> None:
    want_preview = "--preview" in argv
    names = list(PAGES) if "--all" in argv else [a for a in argv if not a.startswith("--")] or ["main"]
    sh = Shooter()
    for v in names:
        page, d, secs, stages = PAGES[v]
        base = page.as_uri()
        for lang in ("en", "vi"):
            for s in secs:
                stage = "&stage=wait" if stages else ""
                sh.shot(f"{base}?shot={s}&lang={lang}{stage}", d / "img" / f"{s}-{lang}.png")
                print(f"{v} {lang} {s}")
            if stages:
                frames = []
                for st in stages:
                    f = d / "img" / f"_demo-{lang}-{st}.png"
                    sh.shot(f"{base}?shot=demo&lang={lang}&stage={st}", f)
                    frames.append(f)
                apng(frames, d / "img" / f"demo-{lang}.png")
                for f in frames:
                    f.unlink()
                print(f"{v} {lang} demo ({len(frames)} khung)")
            md = d / ("README.md" if lang == "en" else "README.vi.md")
            md.write_text(readme(page, d, secs, lang, bool(stages)), encoding="utf-8")
            if want_preview:
                preview(md, lang, OUT / v)
        size = sum(p.stat().st_size for p in (d / "img").glob("*.png")) // 1024
        print(f"-> {d.relative_to(ROOT)}  ({size} KB ảnh)")


if __name__ == "__main__":
    main(sys.argv[1:])
