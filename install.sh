#!/bin/bash
# Cài hoặc cập nhật Wisp trên macOS bằng một lệnh, không qua trình duyệt:
#
#   curl -fsSL https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.sh | bash
#
# File tải bằng curl không mang thuộc tính com.apple.quarantine nên Gatekeeper không chặn. Script tải
# wisp-macos-universal2.dmg của bản mới nhất, so SHA256 với SHA256SUMS.txt, chép Wisp.app vào
# /Applications (không có quyền ghi thì ~/Applications; đổi bằng biến WISP_INSTALL_DIR) rồi mở app.
# Toàn bộ nằm trong main() để bash chỉ chạy khi đã nhận đủ script.
set -euo pipefail

main() {
    local base="https://github.com/hakienit/pet-tracker/releases/latest/download"
    local asset="wisp-macos-universal2.dmg"
    local app_dir="${WISP_INSTALL_DIR:-/Applications}"
    if [ ! -w "$app_dir" ]; then
        app_dir="$HOME/Applications"
        mkdir -p "$app_dir"
    fi
    tmp=$(mktemp -d)
    mnt=""
    trap 'if [ -n "$mnt" ]; then hdiutil detach -quiet "$mnt" || true; fi; rm -rf "$tmp"' EXIT

    echo "Downloading $asset ..."
    curl -fsSL -o "$tmp/$asset" "$base/$asset"
    curl -fsSL -o "$tmp/SHA256SUMS.txt" "$base/SHA256SUMS.txt"
    local want got
    want=$(awk -v f="$asset" '$2 == f || $2 == "*" f { print $1; exit }' "$tmp/SHA256SUMS.txt")
    if [ -z "$want" ]; then
        echo "SHA256SUMS.txt has no entry for $asset" >&2
        exit 1
    fi
    got=$(shasum -a 256 "$tmp/$asset" | awk '{ print $1 }')
    if [ "$got" != "$want" ]; then
        echo "SHA256 mismatch for $asset (expected $want, got $got). Nothing was installed." >&2
        exit 1
    fi

    mkdir "$tmp/mnt"
    hdiutil attach -quiet -nobrowse -readonly -mountpoint "$tmp/mnt" "$tmp/$asset"
    mnt="$tmp/mnt"
    [ -d "$mnt/Wisp.app" ] || { echo "$asset does not contain Wisp.app" >&2; exit 1; }

    if pkill -x Wisp 2>/dev/null; then
        echo "Closing the running Wisp ..."
        sleep 2
    fi
    rm -rf "$app_dir/Wisp.app"
    cp -R "$mnt/Wisp.app" "$app_dir/"
    xattr -dr com.apple.quarantine "$app_dir/Wisp.app" 2>/dev/null || true

    echo "Installed Wisp to $app_dir/Wisp.app"
    open "$app_dir/Wisp.app"
}

main "$@"
