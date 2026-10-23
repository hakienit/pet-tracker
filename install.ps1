# Cài hoặc cập nhật Wisp trên Windows bằng một lệnh, không qua trình duyệt:
#
#   irm https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.ps1 | iex
#
# File tải bằng Invoke-WebRequest không mang Mark of the Web nên SmartScreen không chặn. Script tải
# wisp-win-x64.zip của bản mới nhất, so SHA256 với SHA256SUMS.txt, giải nén vào
# %LOCALAPPDATA%\Programs\Wisp (đổi bằng biến môi trường WISP_INSTALL_DIR), giữ config.json, tạo
# shortcut trong Start Menu rồi mở app.
# Thông báo để tiếng Anh không dấu: PowerShell 5.1 đọc script không BOM theo mã ANSI, chữ có dấu sẽ vỡ.
# Máy công ty có thể khoá PowerShell ở Constrained Language Mode: chỉ gọi được method của vài kiểu lõi và
# không tạo được COM object. Script tránh .NET tĩnh, chỗ nào không tránh được thì bọc try.
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'  # PowerShell 5.1: vẽ progress làm Invoke-WebRequest chậm hẳn
    # CLM chặn dòng này; khi đó Invoke-WebRequest có thể hỏng TLS và $get chuyển sang curl.exe
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
    $get = {
        param($url, $out)
        try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out }
        catch {
            curl.exe -fsSL -o $out $url
            if ($LASTEXITCODE) { throw "Download failed: $url" }
        }
    }

    $base = 'https://github.com/hakienit/pet-tracker/releases/latest/download'
    $asset = 'wisp-win-x64.zip'
    $dir = if ($env:WISP_INSTALL_DIR) { $env:WISP_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\Wisp' }
    $dir = (New-Item -ItemType Directory -Force -Path $dir).FullName
    $exe = Join-Path $dir 'wisp.exe'
    $tmp = Join-Path $env:TEMP ('wisp-install-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        Write-Host "Downloading $asset ..."
        $zip = Join-Path $tmp $asset
        & $get "$base/$asset" $zip
        $sums = Join-Path $tmp 'SHA256SUMS.txt'
        & $get "$base/SHA256SUMS.txt" $sums
        $line = Get-Content -LiteralPath $sums | Where-Object { $_ -match ('^[0-9a-fA-F]{64}\s+\*?' + [regex]::Escape($asset) + '\s*$') } | Select-Object -First 1
        if (-not $line) { throw "SHA256SUMS.txt has no entry for $asset" }
        $want = ($line -split '\s+')[0]
        # Get-FileHash và Expand-Archive là hàm script, có thể bị CLM chặn; certutil / tar.exe có sẵn trên Windows 10+
        try { $got = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash }
        catch { $got = (certutil.exe -hashfile $zip SHA256)[1] -replace ' ', '' }
        if ($got -ne $want) { throw "SHA256 mismatch for $asset (expected $want, got $got). Nothing was installed." }

        $new = Join-Path $tmp 'new'
        try { Expand-Archive -LiteralPath $zip -DestinationPath $new }
        catch {
            New-Item -ItemType Directory -Force -Path $new | Out-Null
            & "$env:SystemRoot\System32\tar.exe" -xf $zip -C $new  # gọi thẳng: tar của Git hiểu "C:" là máy remote
            if ($LASTEXITCODE) { throw "Could not extract $asset" }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $new 'wisp.exe'))) { throw "$asset does not contain wisp.exe" }

        # Chỉ tắt Wisp chạy từ chính thư mục cài; bản ở chỗ khác thì để người dùng tự thoát.
        $running = @(Get-Process -Name wisp -ErrorAction SilentlyContinue)
        $here = @($running | Where-Object { $_.Path -ieq $exe })
        $others = @($running | Where-Object { $here.Id -notcontains $_.Id })
        if ($here.Count) {
            Write-Host 'Closing the running Wisp ...'
            $here | Stop-Process -Force
            $here | Wait-Process -Timeout 15 -ErrorAction SilentlyContinue
        }

        # Chỉ xoá file của Wisp (thư mục cài có thể bị đặt nhầm vào chỗ có file khác); config.json giữ nguyên.
        foreach ($n in 'wisp.exe', '_internal', 'config.example.json', 'README.md') {
            $p = Join-Path $dir $n
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
        }
        Copy-Item -Path (Join-Path $new '*') -Destination $dir -Recurse -Force
        Get-ChildItem -LiteralPath $dir -Recurse -File | Unblock-File

        $lnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Wisp.lnk'
        $menu = ''
        try {
            $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
            $sc.TargetPath = $exe
            $sc.WorkingDirectory = $dir
            $sc.Save()
            $menu = ' (Start Menu: Wisp)'
        } catch {
            Write-Warning "Could not create the Start Menu shortcut (PowerShell is restricted). Open $exe directly."
        }

        $ver = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
        Write-Host "Installed Wisp $ver to $dir$menu"
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
