#!/usr/bin/env bash
# Build on a Linux x86_64 computer with Internet access and tkinter available.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
command -v curl >/dev/null || { echo 'Instale curl'; exit 1; }
command -v python3 >/dev/null || { echo 'Instale python3'; exit 1; }
python3 -m venv .build-venv
.build-venv/bin/pip install --upgrade pip pyinstaller -r requirements.txt
.build-venv/bin/pyinstaller --noconfirm --clean --onedir --windowed --name madventure-studio --hidden-import tkinter --collect-all cv2 main.py
APPDIR="$PWD/MadventureStudio.AppDir"
rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp -a dist/madventure-studio "$APPDIR/usr/bin/"
cat > "$APPDIR/AppRun" <<'APP'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/madventure-studio/madventure-studio" "$@"
APP
chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/madventure-studio.desktop" <<'DESK'
[Desktop Entry]
Name=Madventure Stitch Studio
Exec=madventure-studio
Icon=madventure-studio
Type=Application
Categories=Graphics;Photography;
Terminal=false
DESK
cat > "$APPDIR/madventure-studio.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><rect width="128" height="128" rx="24" fill="#132640"/><circle cx="47" cy="64" r="30" stroke="#6bd0e3" stroke-width="7" fill="none"/><circle cx="81" cy="64" r="30" stroke="#f3c868" stroke-width="7" fill="none"/></svg>
SVG
cp "$APPDIR/madventure-studio.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
if ! command -v appimagetool >/dev/null; then
  echo 'Baixando appimagetool...'
  curl -fL 'https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage' -o appimagetool
  chmod +x appimagetool
  APPIMAGETOOL="$PWD/appimagetool"
else APPIMAGETOOL="$(command -v appimagetool)"; fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$PWD/Madventure-Stitch-Studio-x86_64.AppImage"
chmod +x "$PWD/Madventure-Stitch-Studio-x86_64.AppImage"
echo 'PRONTO: Madventure-Stitch-Studio-x86_64.AppImage'
