#!/bin/bash
# Double-click in Finder, or run ./start-macos.command from Terminal.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
fail() { printf '\nStartup failed: %s\n' "$*" >&2; exit 1; }
trap 'code=$?; if [ "$code" -ne 0 ]; then printf "\nReview the error above, then run this launcher again.\n" >&2; fi' EXIT
[ "$(uname -s)" = Darwin ] || fail "This launcher is for macOS. Use start-windows.cmd on Windows."
if ! command -v uv >/dev/null 2>&1 || ! uv --version >/dev/null 2>&1; then
  echo "Installing uv from its official installer..."
  curl --fail --location --silent --show-error https://astral.sh/uv/install.sh | sh
fi
command -v uv >/dev/null 2>&1 || fail "uv installation failed. See https://docs.astral.sh/uv/"
need_node=0
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 24 ? 0 : 1)'; then need_node=1; fi
skip_ocr=0
for argument in "$@"; do [ "$argument" != "--skip-ocr" ] || skip_ocr=1; done
need_ocr=0
if [ "$skip_ocr" -eq 0 ] && ! command -v tesseract >/dev/null 2>&1; then need_ocr=1; fi
if [ "$need_node" -eq 1 ] || [ "$need_ocr" -eq 1 ]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Installing Homebrew. Its installer may request your macOS password..."
    /bin/bash -c "$(curl --fail --location --silent --show-error https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  fi
  command -v brew >/dev/null 2>&1 || fail "Homebrew could not be installed. Install it from https://brew.sh and retry."
  if [ "$need_node" -eq 1 ]; then
    if brew list --versions node@24 >/dev/null 2>&1; then brew reinstall node@24; else brew install node@24; fi
    export PATH="$(brew --prefix node@24)/bin:$PATH"
  fi
  if [ "$need_ocr" -eq 1 ]; then brew install tesseract; fi
fi
# A keg-only Node installation may already exist from a previous launch.
if command -v brew >/dev/null 2>&1 && [ -d "$(brew --prefix)/opt/node@24/bin" ]; then
  export PATH="$(brew --prefix)/opt/node@24/bin:$PATH"
fi
uv python install 3.11
exec uv run --no-project --python 3.11 scripts/start.py "$@"
