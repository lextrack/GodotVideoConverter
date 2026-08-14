#!/usr/bin/env bash
set -euo pipefail

# Builds a self-contained AppImage for the Python/Qt application. FFmpeg is
# deliberately *not* bundled: the application resolves ffmpeg/ffprobe from PATH.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "AppImage builds must run on Linux."
  exit 1
fi

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|aarch64) ;;
  *)
    echo "Unsupported architecture: $ARCH (supported: x86_64, aarch64)."
    exit 1
    ;;
esac

command -v python >/dev/null 2>&1 || {
  echo "Python 3.11+ was not found in PATH."
  exit 1
}
if ! python -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
  echo "Python 3.11+ is required to build the AppImage."
  exit 1
fi

APP_NAME="godot-video-converter"
VERSION="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
APPIMAGETOOL_VERSION="12"
BUILD_DIR="$ROOT_DIR/.appimage"
APPDIR="$BUILD_DIR/AppDir"
TOOL_CACHE="$BUILD_DIR/tools"
OUTPUT="$ROOT_DIR/dist/${APP_NAME}-${VERSION}-${ARCH}.AppImage"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$TOOL_CACHE" "$ROOT_DIR/dist"

python -m pip install -e ".[release]"
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath dist \
  --workpath .pyinstaller/build \
  gvc.spec

cp -a "$ROOT_DIR/dist/gvc/." "$APPDIR/usr/bin/"
cp "$ROOT_DIR/Assets/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$HERE/usr/bin/gvc" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Godot Video Converter
Comment=Convert video and audio for Godot projects
Exec=gvc
Icon=${APP_NAME}
Categories=AudioVideo;AudioVideoEditing;Utility;
Terminal=false
EOF
cp "$APPDIR/${APP_NAME}.desktop" "$APPDIR/usr/share/applications/${APP_NAME}.desktop"
ln -s "usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png" "$APPDIR/${APP_NAME}.png"
ln -s "${APP_NAME}.png" "$APPDIR/.DirIcon"

APPIMAGETOOL_BIN="${APPIMAGETOOL:-}"
if [[ -z "$APPIMAGETOOL_BIN" ]]; then
  case "$ARCH" in
    x86_64)
      APPIMAGETOOL_SHA256="d918b4df547b388ef253f3c9e7f6529ca81a885395c31f619d9aaf7030499a13"
      ;;
    aarch64)
      APPIMAGETOOL_SHA256="c9d058310a4e04b9fbbd81340fff2b5fb44943a630b31881e321719f271bd41a"
      ;;
  esac

  APPIMAGETOOL_BIN="$TOOL_CACHE/appimagetool-${APPIMAGETOOL_VERSION}-${ARCH}.AppImage"
  command -v sha256sum >/dev/null 2>&1 || {
    echo "sha256sum is required to verify appimagetool (or set APPIMAGETOOL)."
    exit 1
  }
  if [[ ! -f "$APPIMAGETOOL_BIN" ]]; then
    command -v curl >/dev/null 2>&1 || {
      echo "curl is required to download appimagetool (or set APPIMAGETOOL)."
      exit 1
    }
    APPIMAGETOOL_DOWNLOAD="$APPIMAGETOOL_BIN.download"
    rm -f "$APPIMAGETOOL_DOWNLOAD"
    curl -fL "https://github.com/AppImage/AppImageKit/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage" \
      -o "$APPIMAGETOOL_DOWNLOAD"
    echo "${APPIMAGETOOL_SHA256}  ${APPIMAGETOOL_DOWNLOAD}" | sha256sum --check --status || {
      rm -f "$APPIMAGETOOL_DOWNLOAD"
      echo "Downloaded appimagetool failed SHA-256 verification."
      exit 1
    }
    mv "$APPIMAGETOOL_DOWNLOAD" "$APPIMAGETOOL_BIN"
  fi
  echo "${APPIMAGETOOL_SHA256}  ${APPIMAGETOOL_BIN}" | sha256sum --check --status || {
    echo "Cached appimagetool failed SHA-256 verification."
    exit 1
  }
  chmod +x "$APPIMAGETOOL_BIN"
fi

if ! command -v "$APPIMAGETOOL_BIN" >/dev/null 2>&1 && [[ ! -x "$APPIMAGETOOL_BIN" ]]; then
  echo "APPIMAGETOOL is not executable: $APPIMAGETOOL_BIN"
  exit 1
fi

rm -f "$OUTPUT"
ARCH="$ARCH" VERSION="$VERSION" APPIMAGE_EXTRACT_AND_RUN=1 \
  "$APPIMAGETOOL_BIN" "$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"

echo "AppImage ready at: $OUTPUT"
echo "FFmpeg is not included; users need ffmpeg and ffprobe available in PATH."
