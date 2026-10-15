"""Kiểm tra và cài bản mới từ GitHub Releases.

- Kiểm tra: GET https://api.github.com/repos/hakienit/pet-tracker/releases/latest. Endpoint này của
  GitHub đã bỏ qua release draft và pre-release; widget vẫn kiểm tra lại hai cờ đó cho chắc.
  So tag (vd. "v0.2.0") với __version__.
- Cài (chỉ khi chạy từ exe đã build bằng PyInstaller):
  1. tải asset `pet-tracker-<ver>-win-x64.zip` và `SHA256SUMS.txt` của release vào thư mục tạm;
  2. so SHA256 của zip với dòng tương ứng trong SHA256SUMS.txt, sai thì dừng;
  3. giải nén vào thư mục tạm, kiểm tra có `pet-tracker.exe`;
  4. chạy script PowerShell (ẩn) chờ process hiện tại thoát, đổi tên thư mục cài thành bản dự phòng,
     chép bản mới vào, giữ lại `config.json` cũ, mở lại exe; lỗi thì khôi phục bản dự phòng.
  Widget thoát ngay sau khi chạy script. Log của script: %APPDATA%\\pet-tracker\\update.log.
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

REPO = "hakienit/pet-tracker"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
EXE_NAME = "pet-tracker.exe"
SUMS_NAME = "SHA256SUMS.txt"
USER_AGENT = f"pet-tracker/{__version__} (update check)"


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
    return f"pet-tracker-{version.lstrip('vV')}-win-x64.zip"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    return Path(sys.executable).resolve().parent


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
    """Tải + kiểm tra + giải nén. Trả thư mục chứa bản mới (có pet-tracker.exe). Lỗi -> ValueError/OSError."""
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
SWAP_PS1 = r"""
param([int]$WaitPid, [string]$Stage, [string]$Install, [string]$Exe, [string]$Log)
$ErrorActionPreference = 'Stop'
function L($m) { Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding utf8 }
L "update: waiting for pid $WaitPid"
try { Wait-Process -Id $WaitPid -Timeout 60 -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 500
$backup = "$Install.old"
try {
  if (Test-Path $backup) { Remove-Item $backup -Recurse -Force }
  Rename-Item -Path $Install -NewName (Split-Path $backup -Leaf)
  L "update: moved $Install -> $backup"
  try {
    Copy-Item -Path $Stage -Destination $Install -Recurse -Force
    if (Test-Path "$backup\config.json") { Copy-Item "$backup\config.json" "$Install\config.json" -Force }
    L "update: copied new version into $Install"
  } catch {
    L "update: copy failed: $_ ; restoring backup"
    if (Test-Path $Install) { Remove-Item $Install -Recurse -Force }
    Rename-Item -Path $backup -NewName (Split-Path $Install -Leaf)
    throw
  }
  Start-Process -FilePath (Join-Path $Install $Exe) -WorkingDirectory $Install
  L "update: started new version"
  Start-Sleep -Seconds 3
  Remove-Item $backup -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item (Split-Path $Stage -Parent) -Recurse -Force -ErrorAction SilentlyContinue
  L "update: done"
} catch {
  L "update: FAILED: $_"
  try {
    if (Test-Path (Join-Path $Install $Exe)) {
      Start-Process -FilePath (Join-Path $Install $Exe) -WorkingDirectory $Install
      L "update: restarted previous version"
    } else { L "update: previous version not found at $Install" }
  } catch { L "update: could not restart previous version: $_" }
  Start-Sleep -Seconds 1
  exit 1
}
"""


def launch_swap(stage: Path, target_dir: Path, wait_pid: int, exe_name: str = EXE_NAME, log_file=None,
                env=None) -> subprocess.Popen:
    """Chạy script PowerShell ẩn để thay thư mục cài sau khi process wait_pid thoát."""
    script = Path(tempfile.gettempdir()) / f"pet-tracker-update-{os.getpid()}.ps1"
    script.write_text(SWAP_PS1, encoding="utf-8-sig")
    if log_file is None:
        log_file = Path(os.environ.get("APPDATA", str(Path.home()))) / "pet-tracker" / "update.log"
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
            "-File", str(script), "-WaitPid", str(int(wait_pid)), "-Stage", str(stage),
            "-Install", str(target_dir), "-Exe", exe_name, "-Log", str(log_file)]
    # NEW_PROCESS_GROUP | NO_WINDOW. Không dùng DETACHED_PROCESS: PowerShell không có console sẽ
    # thoát ngay (exit 0) mà không chạy script.
    flags = 0x00000200 | 0x08000000
    return subprocess.Popen(args, creationflags=flags, env=env, close_fds=True)
