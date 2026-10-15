"""Windows: script PowerShell thay thư mục cài sau khi app thoát (dùng cho cập nhật một chạm)."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

EXE_NAME = "pet-tracker.exe"

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
