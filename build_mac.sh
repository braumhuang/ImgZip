#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[ERROR] build_mac.sh must be run on macOS." >&2
  exit 1
fi

# Prefer project-local environments in this order: .venv, then venv.
# Only fall back to an explicitly supplied PY, then the system python3.
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
  PY_SOURCE="project .venv"
elif [[ -x "$ROOT/venv/bin/python" ]]; then
  PY="$ROOT/venv/bin/python"
  PY_SOURCE="project venv"
elif [[ -n "${PY:-}" ]]; then
  PY_SOURCE="PY override"
else
  PY="$(command -v python3 || true)"
  PY_SOURCE="system python3"
fi

if [[ -z "$PY" ]] || { ! command -v "$PY" >/dev/null 2>&1 && [[ ! -x "$PY" ]]; }; then
  echo "[ERROR] Python executable not found. Create .venv/ or venv/, or install python3." >&2
  exit 1
fi

PY_VERSION="$("$PY" -c 'import platform; print(platform.python_version())')"
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8, 5) else 1)'; then
  echo "[ERROR] Python 3.8.5 or later is required; detected $PY_VERSION ($PY)." >&2
  exit 1
fi

ARCH="$("$PY" -c 'import platform; print(platform.machine())')"
case "$ARCH" in
  x86_64|arm64) ;;
  *) echo "[ERROR] Unsupported Python architecture: $ARCH" >&2; exit 1 ;;
esac

MACOS_VERSION="$(sw_vers -productVersion)"
MACOS_MAJOR="${MACOS_VERSION%%.*}"
if (( MACOS_MAJOR < 11 )); then
  echo "[ERROR] Build host macOS 11 or later is required; found $MACOS_VERSION." >&2
  exit 1
fi

export MACOSX_DEPLOYMENT_TARGET=11.0

echo "[1/6] Python: $PY ($PY_VERSION, $ARCH; selected from $PY_SOURCE)"
"$PY" -m pip install --upgrade pip

# Install application dependencies, including the fixed Pillow version.
echo "[2/6] Install application dependencies (Pillow 10.4.0)..."
"$PY" -m pip install -r requirements.txt
"$PY" - <<'PY_VERIFY'
import sys
import PIL
from PyQt5.QtCore import PYQT_VERSION_STR

if sys.version_info < (3, 8, 5):
    raise SystemExit("Python 3.8.5 or later is required")
if PYQT_VERSION_STR != "5.15.11":
    raise SystemExit("Unexpected PyQt5 version: " + PYQT_VERSION_STR)
if PIL.__version__ != "10.4.0":
    raise SystemExit("Pillow must be exactly 10.4.0; found " + PIL.__version__)
print("PyQt5", PYQT_VERSION_STR, "| Pillow", PIL.__version__)
PY_VERIFY

# PyInstaller selects the newest release compatible with the selected Python.
echo "[3/6] Install compatible macOS packaging tools..."
"$PY" -m pip install --upgrade "pyinstaller>=5.13.2,<7"

APP_VERSION="$("$PY" -c 'from imgzip import APP_VERSION; print(APP_VERSION)')"
echo "[4/6] Synchronize APP_VERSION: $APP_VERSION"
"$PY" tools/sync_version.py "$APP_VERSION"

rm -rf "dist/ImgZip.app" "build/ImgZip"
mkdir -p dist

echo "[5/6] Build one-file macOS application ($ARCH)..."
"$PY" -m PyInstaller \
  --noconfirm --clean --onefile --windowed \
  --name ImgZip \
  --icon "assets/icon.icns" \
  --add-data "assets:assets" \
  --osx-bundle-identifier "com.imgzip.app" \
  --target-arch "$ARCH" \
  --distpath "dist" --workpath "build" \
  "main.py"

APP="dist/ImgZip.app"
PLIST="$APP/Contents/Info.plist"
APP_BIN="$APP/Contents/MacOS/ImgZip"
if [[ ! -d "$APP" || ! -f "$PLIST" || ! -x "$APP_BIN" ]]; then
  echo "[ERROR] PyInstaller did not create a valid ImgZip.app bundle." >&2
  exit 1
fi

"$PY" - "$PLIST" "$APP_VERSION" <<'PY_META'
import plistlib
import sys
from pathlib import Path

plist_path = Path(sys.argv[1])
version = sys.argv[2]
with plist_path.open("rb") as stream:
    data = plistlib.load(stream)
data["CFBundleShortVersionString"] = version
data["CFBundleVersion"] = version
data["LSMinimumSystemVersion"] = "11.0"
data["CFBundleDisplayName"] = "ImgZip"
with plist_path.open("wb") as stream:
    plistlib.dump(data, stream)
PY_META

BUILT_ARCH="$(lipo -archs "$APP_BIN")"
if [[ "$BUILT_ARCH" != "$ARCH" ]]; then
  echo "[ERROR] App architecture mismatch: expected $ARCH, got $BUILT_ARCH." >&2
  exit 1
fi

# Ad-hoc signature permits local testing; public distribution needs Developer ID + notarization.
codesign --force --deep --sign - "$APP"
codesign --verify --deep "$APP"

echo "[6/6] Verify output..."
echo "Output: $APP"
echo "Version: $APP_VERSION"
echo "Architecture: $BUILT_ARCH"
echo "Minimum macOS: 11.0"
echo "Python: $PY_VERSION"
echo "Python source: $PY_SOURCE"
echo "[SUCCESS] ImgZip v$APP_VERSION macOS one-file app build completed."
