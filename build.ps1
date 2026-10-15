# Build Wisp cho Windows bằng PyInstaller (dạng thư mục, không console) + zip portable.
#
#   pwsh -File build.ps1                 # dùng "python" trên PATH
#   pwsh -File build.ps1 -Python "C:\Python313\python.exe"
#   pwsh -File build.ps1 -AppsDir D:\apps   # thêm: chép vào D:\apps\Wisp\<version>
#
# Output:
#   dist\wisp\wisp.exe                  (chạy trực tiếp)
#   dist\wisp-<version>-win-x64.zip
#
# Ghi chú: dùng --onedir thay vì --onefile vì khởi động nhanh hơn và ít bị antivirus báo nhầm.
# Nếu PyInstaller chưa hỗ trợ bản Python đang dùng, cài Python 3.13 rồi truyền -Python.
param(
    [string]$Python = "python",
    # Nếu có: chép bản build vào <AppsDir>\Wisp\<version>, cùng version thì thay bản cũ (giữ config.json)
    [string]$AppsDir = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (& $Python -c "import sys; sys.path.insert(0, '.'); import pet_tracker; print(pet_tracker.__version__)").Trim()
$pyver = (& $Python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
Write-Host "Wisp $version, Python $pyver"

& $Python -m pip install --upgrade "pyinstaller==6.22.3" | Out-Host

# Icon (tạo lại nếu thiếu)
if (-not (Test-Path "assets\wisp.ico")) { & $Python tools\make_icon.py | Out-Host }

# Version info cho file exe (Properties -> Details)
$parts = ($version -split '[.-]')[0..2] + @('0')
$tuple = ($parts[0..3] | ForEach-Object { [int]$_ }) -join ', '
New-Item -ItemType Directory -Force build | Out-Null
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($tuple), prodvers=($tuple), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Vinova'),
      StringStruct('FileDescription', 'Wisp - Claude Code usage widget'),
      StringStruct('FileVersion', '$version'),
      StringStruct('InternalName', 'wisp'),
      StringStruct('OriginalFilename', 'wisp.exe'),
      StringStruct('ProductName', 'Wisp'),
      StringStruct('ProductVersion', '$version')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Encoding utf8 build\version_info.txt

& $Python -m PyInstaller --noconfirm --clean --onedir --noconsole `
    --name wisp `
    --icon assets\wisp.ico `
    --version-file build\version_info.txt `
    --add-data "assets\wisp.ico;assets" `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller lỗi (exit $LASTEXITCODE)" }

# Kèm README + config mẫu, rồi zip bản portable
Copy-Item README.md, config.example.json dist\wisp\ -Force
$zip = "dist\wisp-$version-win-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path dist\wisp\* -DestinationPath $zip
Write-Host "Done -> $PSScriptRoot\dist\wisp\wisp.exe"
Write-Host "Zip  -> $PSScriptRoot\$zip"

if ($AppsDir) {
    $dest = Join-Path $AppsDir "Wisp\$version"
    $cfg = Join-Path $dest "config.json"
    $keep = Join-Path $env:TEMP "wisp-config-$PID.json"
    if (Test-Path $cfg) { Copy-Item $cfg $keep -Force }
    # Wisp đang chạy từ thư mục này thì Remove-Item lỗi: thoát app trước rồi build lại
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item dist\wisp\* $dest -Recurse -Force
    if (Test-Path $keep) { Move-Item $keep $cfg -Force }
    Write-Host "App  -> $dest\wisp.exe"
}
