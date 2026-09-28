#!/bin/sh
set -eu
SCRIPT_DIR=$(dirname -- "$0")
cd "$SCRIPT_DIR"
PYTHON="${PYTHON:-python3.13}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    printf '%s\n' 'Kaynak sürüm Python 3.13 gerektirir. Python kurmadan çalıştırmak için AppImage veya .deb paketini kullanın.' >&2
    exit 1
fi
if [ ! -x .venv-linux/bin/python ]; then
    "$PYTHON" -m venv .venv-linux
    .venv-linux/bin/python -m pip install -r packaging/linux/requirements-build.txt
    .venv-linux/bin/python -m pip install --no-deps .
fi
exec .venv-linux/bin/python -m pixel_nonograms "$@"
