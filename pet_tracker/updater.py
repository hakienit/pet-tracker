"""Kiểm tra và cài bản mới từ GitHub Releases.

- Kiểm tra: GET https://api.github.com/repos/hakienit/pet-tracker/releases/latest. Endpoint này của
  GitHub đã bỏ qua release draft và pre-release; widget vẫn kiểm tra lại hai cờ đó cho chắc.
  So tag (vd. "v0.2.0") với __version__.
- Cài (chỉ khi chạy từ exe đã build bằng PyInstaller, hiện chỉ Windows; macOS mở trang release):
  1. tải asset `wisp-<ver>-win-x64.zip` và `SHA256SUMS.txt` của release vào thư mục tạm;
  2. so SHA256 của zip với dòng tương ứng trong SHA256SUMS.txt, sai thì dừng;
  3. giải nén vào thư mục tạm, kiểm tra có `wisp.exe`;
  4. chạy script PowerShell (ẩn) chờ process hiện tại thoát, đổi tên thư mục cài thành bản dự phòng,
     chép bản mới vào, giữ lại `config.json` cũ, mở lại exe; lỗi thì khôi phục bản dự phòng.
  Widget thoát ngay sau khi chạy script. Log của script: %APPDATA%\\Wisp\\update.log.
- Chạy từ source: chỉ mở trang release (không tự thay code).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import __version__
from . import platform as plat

REPO = "hakienit/pet-tracker"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
EXE_NAME = "wisp.exe"
SUMS_NAME = "SHA256SUMS.txt"
USER_AGENT = f"Wisp/{__version__} (update check)"


# ---------------------------------------------------------------- version
def parse_version(s: str) -> tuple:
    """'v0.12.3' -> (0, 12, 3). Phần không phải số (vd. '-rc1') bị bỏ qua."""
    s = (s or "").strip().lstrip("vV")
    nums = []
    for part in re.split(r"[.\-+]", s):
        if not part.isdigit():
            break
        nums.append(int(part))
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def asset_name(version: str) -> str:
    """Tên file của bản build cho hệ điều hành đang chạy (Windows: ...-win-x64.zip)."""
    return plat.update_asset_name(version)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def can_self_update() -> bool:
    """Cập nhật một chạm chỉ khi chạy từ bản build và nền tảng hỗ trợ (hiện chỉ Windows)."""
    return is_frozen() and plat.CAN_SELF_UPDATE


def install_dir() -> Path:
    return plat.install_dir()


# ---------------------------------------------------------------- http
def _get(url: str, timeout: float, accept: str = "application/octet-stream") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _download(url: str, dest: Path, timeout: float = 60.0, progress=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)


# ---------------------------------------------------------------- check
def check(api_url: str = API_LATEST, current: str = __version__, timeout: float = 15.0) -> dict:
    """Trả {ok, available, version, tag, html_url, notes, zip_url, sums_url, error}."""
    out = {"ok": False, "available": False, "current": current, "checked_at": time.time()}
    try:
        data = json.loads(_get(api_url, timeout, accept="application/vnd.github+json").decode("utf-8"))
    except urllib.error.HTTPError as e:
        out["error"] = "chưa có release nào" if e.code == 404 else f"HTTP {e.code}"
        out["ok"] = e.code == 404  # 404 = repo chưa có release: không phải lỗi
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:160]
        return out
    tag = data.get("tag_name") or ""
    out.update(ok=True, tag=tag, version=tag.lstrip("vV"), html_url=data.get("html_url") or RELEASES_PAGE,
               notes=(data.get("body") or "").strip())
    if data.get("draft") or data.get("prerelease"):
        return out
    assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets") or []}
    out["zip_url"] = assets.get(asset_name(tag))
    out["sums_url"] = assets.get(SUMS_NAME)
    out["available"] = is_newer(tag, current)
    return out


# ---------------------------------------------------------------- download + verify
def expected_sha256(sums_text: str, filename: str):
    for line in sums_text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_stage(info: dict, progress=None, workdir=None) -> Path:
    """Tải + kiểm tra + giải nén. Trả thư mục chứa bản mới (có wisp.exe). Lỗi -> ValueError/OSError."""
    if not info.get("zip_url") or not info.get("sums_url"):
        raise ValueError(f"release {info.get('tag')} thiếu {asset_name(info.get('tag', ''))} hoặc {SUMS_NAME}")
    work = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="pet-update-"))
    work.mkdir(parents=True, exist_ok=True)
    zname = asset_name(info["tag"])
    zpath = work / zname
    sums = _get(info["sums_url"], 30).decode("utf-8", "replace")
    want = expected_sha256(sums, zname)
    if not want:
        raise ValueError(f"{SUMS_NAME} không có dòng cho {zname}")
    _download(info["zip_url"], zpath, progress=progress)
    got = sha256_file(zpath)
    if got != want:
        zpath.unlink(missing_ok=True)
        raise ValueError(f"SHA256 không khớp ({got[:12]}… ≠ {want[:12]}…), đã huỷ cập nhật")
    stage = work / "new"
    if stage.exists():
        shutil.rmtree(stage)
    with zipfile.ZipFile(zpath) as z:
        for m in z.namelist():  # chặn path traversal
            if m.startswith(("/", "\\")) or ".." in Path(m).parts or ":" in m:
                raise ValueError(f"zip có đường dẫn không hợp lệ: {m}")
        z.extractall(stage)
    if not (stage / EXE_NAME).exists():
        inner = [p for p in stage.iterdir() if p.is_dir() and (p / EXE_NAME).exists()]
        if len(inner) == 1:
            stage = inner[0]
        else:
            raise ValueError(f"zip không chứa {EXE_NAME}")
    return stage


# ---------------------------------------------------------------- swap
def launch_swap(stage: Path, target_dir: Path, wait_pid: int, exe_name: str = EXE_NAME, log_file=None, env=None):
    """Thay thư mục cài sau khi wait_pid thoát (Windows: script PowerShell, xem platform/win_update.py)."""
    if not plat.CAN_SELF_UPDATE:
        raise RuntimeError("nền tảng này chưa hỗ trợ cập nhật một chạm")
    return plat.launch_swap(stage, target_dir, wait_pid, exe_name=exe_name, log_file=log_file, env=env)
