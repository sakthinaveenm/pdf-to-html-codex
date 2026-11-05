# Installation

Use Python 3.11 and Node 22 or newer. Commands assume the repository root. `uv.lock` files and `frontend/package-lock.json` pin dependencies. Prefer `uv sync --locked` and `npm ci` for reproduction.

```sh
uv python install 3.11
uv sync --locked --project backend --extra test --extra docling
cd frontend
npm ci
npm run build:reader
npx playwright install chromium
cd ..
cp .env.example .env
```

For a smaller CPU setup omit the Docling extra. The exact main Python executable is `backend/.venv/bin/python` on macOS/Linux or `backend\.venv\Scripts\python.exe` on Windows. Main backend dependencies include no Marker installation.

## Optional Marker profile

Marker 1.9.3 is the tested legacy adapter. It pins older dependencies with unresolved advisories; its source/model terms differ from current upstream. Review [LICENSES.md](LICENSES.md) and the audit report before enabling it on untrusted documents or redistributing it. The default main runtime stays independent of these constraints.

```sh
uv sync --locked --project engines/marker
# .env, macOS/Linux:
# PDF_MARKER_PYTHON=./engines/marker/.venv/bin/python
# Windows:
# PDF_MARKER_PYTHON=./engines/marker/.venv/Scripts/python.exe
```

On this development host the already-tested Marker environment is `.venv/bin/python`; the local untracked `.env` points there. New installations should use the locked profile above. AUTO uses Marker if its configured interpreter is available, then Docling, then lightweight extraction. This separation is an operational boundary, not a conclusion about copyleft distribution obligations.

## OCR

macOS: `brew install tesseract tesseract-lang`. Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam tesseract-ocr-hin tesseract-ocr-tel tesseract-ocr-mal`. Add other `tesseract-ocr-<code>` packages as needed.

Windows PowerShell: `winget install --id UB-Mannheim.TesseractOCR`. Add the install directory to PATH. Put the required `.traineddata` files from the official tessdata repository into its `tessdata` directory. Set `TESSDATA_PREFIX` if using a custom directory. Verify with `tesseract --list-langs`.

Use `tessdata_best` for a measured accuracy experiment; `tessdata_fast` favors speed. Do not mix incompatible legacy engine settings for Indic/Arabic packs. All OCR is local.

## Models and hardware

CPU mode is default (`PDF_DEVICE=cpu`). Use `cuda` only with a matching PyTorch CUDA build and enough memory; no 4 GB VRAM fit is promised. Start with one worker. Marker and Docling lazily download weights on first conversion. Warm them once before air-gapped use and retain caches. A missing pack, download failure, unsupported model API or memory limit produces an explicit failed attempt and AUTO fallback diagnostics.

## Start and migrations

Follow README's two-terminal commands from the root. `./scripts/dev.sh` is a convenience on POSIX. New databases initialize at startup. To track the initial schema explicitly:

```sh
PYTHONPATH=backend backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Back up `storage/jobs.sqlite` and document directories together before future migrations. Dockerfile provides an optional API-only container; run the frontend separately and mount `/data`. Do not use Uvicorn `--workers` with this queue design.
