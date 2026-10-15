# Build pet-tracker cho Windows bằng PyInstaller (dạng thư mục, không console) + zip portable.
#
#   pwsh -File build.ps1                 # dùng "python" trên PATH
#   pwsh -File build.ps1 -Python "C:\Python313\python.exe"
#
# Output:
#   dist\pet-tracker\pet-tracker.exe     (chạy trực tiếp)
#   dist\pet-tracker-<version>-win-x64.zip
#
# Ghi chú: dùng --onedir thay vì --onefile vì khởi động nhanh hơn và ít bị antivirus báo nhầm.
# Nếu PyInstaller chưa hỗ trợ bản Python đang dùng, cài Python 3.13 rồi truyền -Python.
param(
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (& $Python -c "import sys; sys.path.insert(0, '.'); import pet_tracker; print(pet_tracker.__version__)").Trim()
$pyver = (& $Python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
Write-Host "pet-tracker $version, Python $pyver"

& $Python -m pip install --upgrade "pyinstaller>=6.10" | Out-Host

# Icon (tạo lại nếu thiếu)
if (-not (Test-Path "assets\pet-tracker.ico")) { & $Python tools\make_icon.py | Out-Host }

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
      StringStruct('FileDescription', 'Claude PET - Claude Code usage widget'),
      StringStruct('FileVersion', '$version'),
      StringStruct('InternalName', 'pet-tracker'),
      StringStruct('OriginalFilename', 'pet-tracker.exe'),
      StringStruct('ProductName', 'Claude PET'),
      StringStruct('ProductVersion', '$version')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Encoding utf8 build\version_info.txt

& $Python -m PyInstaller --noconfirm --clean --onedir --noconsole `
    --name pet-tracker `
    --icon assets\pet-tracker.ico `
    --version-file build\version_info.txt `
    --add-data "assets\pet-tracker.ico;assets" `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller lỗi (exit $LASTEXITCODE)" }

# Kèm README + config mẫu, rồi zip bản portable
Copy-Item README.md, config.example.json dist\pet-tracker\ -Force
$zip = "dist\pet-tracker-$version-win-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path dist\pet-tracker\* -DestinationPath $zip
Write-Host "Done -> $PSScriptRoot\dist\pet-tracker\pet-tracker.exe"
Write-Host "Zip  -> $PSScriptRoot\$zip"
