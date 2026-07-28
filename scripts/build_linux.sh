#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "Missing ffmpeg/ffprobe in PATH. Install them with your distro package manager."
  exit 1
fi

python -m pip install -e ".[build]"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath dist \
  --workpath .pyinstaller/build \
  gvc.spec

echo "Build ready at dist/gvc/"
