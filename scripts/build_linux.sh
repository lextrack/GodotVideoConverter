#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python -m pip install -e ".[build]"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath dist \
  --workpath .pyinstaller/build \
  gvc.spec

echo "Build ready at dist/gvc/"
