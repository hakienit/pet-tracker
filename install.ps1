# Cài hoặc cập nhật Wisp trên Windows bằng một lệnh, không qua trình duyệt:
#
#   irm https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.ps1 | iex
#
# File tải bằng Invoke-WebRequest không mang Mark of the Web nên SmartScreen không chặn. Script tải
# wisp-win-x64.zip của bản mới nhất, so SHA256 với SHA256SUMS.txt, giải nén vào
# %LOCALAPPDATA%\Programs\Wisp (đổi bằng biến môi trường WISP_INSTALL_DIR), giữ config.json, tạo
# shortcut trong Start Menu rồi mở app.
# Thông báo để tiếng Anh không dấu: PowerShell 5.1 đọc script không BOM theo mã ANSI, chữ có dấu sẽ vỡ.
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'  # PowerShell 5.1: vẽ progress làm Invoke-WebRequest chậm hẳn
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $base = 'https://github.com/hakienit/pet-tracker/releases/latest/download'
    $asset = 'wisp-win-x64.zip'
    $dir = if ($env:WISP_INSTALL_DIR) { $env:WISP_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\Wisp' }
    $dir = [IO.Path]::GetFullPath($dir)
    $exe = Join-Path $dir 'wisp.exe'
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('wisp-install-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        Write-Host "Downloading $asset ..."
        $zip = Join-Path $tmp $asset
        Invoke-WebRequest -UseBasicParsing -Uri "$base/$asset" -OutFile $zip
        $sums = Join-Path $tmp 'SHA256SUMS.txt'
        Invoke-WebRequest -UseBasicParsing -Uri "$base/SHA256SUMS.txt" -OutFile $sums
        $line = Get-Content -LiteralPath $sums | Where-Object { $_ -match ('^[0-9a-fA-F]{64}\s+\*?' + [regex]::Escape($asset) + '\s*$') } | Select-Object -First 1
        if (-not $line) { throw "SHA256SUMS.txt has no entry for $asset" }
        $want = ($line -split '\s+')[0]
        $got = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
        if ($got -ne $want) { throw "SHA256 mismatch for $asset (expected $want, got $got). Nothing was installed." }

        $new = Join-Path $tmp 'new'
        Expand-Archive -LiteralPath $zip -DestinationPath $new
        if (-not (Test-Path -LiteralPath (Join-Path $new 'wisp.exe'))) { throw "$asset does not contain wisp.exe" }

        # Chỉ tắt Wisp chạy từ chính thư mục cài; bản ở chỗ khác thì để người dùng tự thoát.
        $running = @(Get-Process -Name wisp -ErrorAction SilentlyContinue)
        $here = @($running | Where-Object { $_.Path -and ([IO.Path]::GetFullPath($_.Path) -ieq $exe) })
        $others = @($running | Where-Object { $here.Id -notcontains $_.Id })
        if ($here.Count) {
            Write-Host 'Closing the running Wisp ...'
            $here | Stop-Process -Force
            $here | Wait-Process -Timeout 15 -ErrorAction SilentlyContinue
        }

        # Chỉ xoá file của Wisp (thư mục cài có thể bị đặt nhầm vào chỗ có file khác); config.json giữ nguyên.
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        foreach ($n in 'wisp.exe', '_internal', 'config.example.json', 'README.md') {
            $p = Join-Path $dir $n
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
        }
        Copy-Item -Path (Join-Path $new '*') -Destination $dir -Recurse -Force
        Get-ChildItem -LiteralPath $dir -Recurse -File | Unblock-File

        $lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'Wisp.lnk'
        $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
        $sc.TargetPath = $exe
        $sc.WorkingDirectory = $dir
        $sc.Save()

        $ver = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
        Write-Host "Installed Wisp $ver to $dir (Start Menu: Wisp)"
        if ($others.Count) {
            Write-Warning ("Another Wisp is still running from " + (($others | ForEach-Object { $_.Path }) -join ', ') +
                           ". Quit it (right-click the widget -> Exit), then open Wisp from the Start Menu.")
        } else {
            Start-Process -FilePath $exe -WorkingDirectory $dir
        }
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
