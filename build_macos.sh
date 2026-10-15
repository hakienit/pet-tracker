#!/usr/bin/env bash
# Build Wisp cho macOS (universal2: Apple Silicon + Intel) bằng PyInstaller, đóng gói .dmg.
#
#   PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 ./build_macos.sh
#
# Yêu cầu: Python từ python.org bản universal2 (có sẵn Tk). Python của Homebrew hoặc setup-python thường
# chỉ có một kiến trúc, PyInstaller --target-arch universal2 sẽ lỗi.
# Output: dist/Wisp.app, dist/wisp-<version>-macos-universal2.dmg
# Bản build KHÔNG ký số / notarize: chỉ ký ad-hoc (Apple Silicon bắt buộc có chữ ký, kể cả ad-hoc).
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
VER="$("$PY" -c 'import pet_tracker; print(pet_tracker.__version__)')"
echo "Wisp $VER, $("$PY" -c 'import platform, sys; print(sys.version.split()[0], platform.machine())')"

"$PY" -m pip install --upgrade "pyinstaller>=6.10"

# Icon .icns từ hình vẽ bằng tools/make_icon.py
mkdir -p build
"$PY" tools/make_icon.py --png-size 1024 --out build/icon_1024.png
ICONSET=build/wisp.iconset
rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" build/icon_1024.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -z "$d" "$d" build/icon_1024.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/wisp.icns

"$PY" -m PyInstaller --noconfirm --clean --windowed \
  --name "Wisp" \
  --osx-bundle-identifier sg.vinova.wisp \
  --target-arch universal2 \
  --icon build/wisp.icns \
  main.py

APP="dist/Wisp.app"
PLIST="$APP/Contents/Info.plist"
plist_set() {  # plist_set <key> <type> <value>
  /usr/libexec/PlistBuddy -c "Set :$1 $3" "$PLIST" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :$1 $2 $3" "$PLIST"
}
plist_set LSUIElement bool true                 # widget nổi: không hiện icon trên Dock
plist_set CFBundleShortVersionString string "$VER"
plist_set CFBundleVersion string "$VER"
plist_set NSAppleEventsUsageDescription string "Wisp dùng AppleScript để chọn đúng tab Terminal/iTerm2 của session khi bạn bấm vào session."

# Info.plist đổi -> ký lại ad-hoc
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# .dmg: app + lối tắt Applications + README
rm -rf build/dmg; mkdir -p build/dmg
cp -R "$APP" build/dmg/
ln -s /Applications build/dmg/Applications
cp README.md build/dmg/
DMG="dist/wisp-$VER-macos-universal2.dmg"
rm -f "$DMG"
hdiutil create -volname "Wisp" -srcfolder build/dmg -ov -format UDZO "$DMG"
lipo -info "$APP/Contents/MacOS/Wisp" || true
echo "Done -> $DMG"
