# Folio — Multilingual PDF to HTML

A local document workspace with a durable SQLite conversion queue, semantic selectable HTML, a TipTap editor, persistent Unicode-aware highlights, PDF.js comparison, and offline exports. No cloud OCR or inference calls. Model engines may download weights on first use.

**Status:** working local application; see [TESTING.md](TESTING.md) and [docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) for measured results and unverified areas. This is not a claim of production readiness or universal PDF accuracy.

## Install

Python 3.11 and Node 22+ are required. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```sh
uv python install 3.11
uv sync --project backend --extra test --extra docling
cd frontend
npm ci
npm run build:reader
npx playwright install chromium
cd ..
cp .env.example .env
```

The base application also runs without Docling: omit `--extra docling`. Digital extraction works with pdfplumber; scanned pages need Tesseract. Marker is an optional isolated legacy profile with important license/security constraints; see [INSTALLATION.md](INSTALLATION.md).

Install OCR:

```sh
# macOS
brew install tesseract tesseract-lang
# Debian / Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam tesseract-ocr-hin tesseract-ocr-tel tesseract-ocr-mal
# Windows PowerShell: then install language data as described in INSTALLATION.md
winget install --id UB-Mannheim.TesseractOCR
```

## Run

Two terminals, both starting at the repository root:

```sh
# macOS / Linux
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Windows PowerShell
$env:PYTHONPATH="backend"
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
cd frontend
npm run dev
```

Open [the workspace](http://127.0.0.1:5173) and [OpenAPI](http://127.0.0.1:8000/docs). On macOS/Linux `./scripts/dev.sh` starts both. Use exactly one Uvicorn process; the queue controls converter concurrency. Keep it bound to loopback.

Choose files or drop up to 20 PDFs. Set document language and Tesseract codes such as `eng+tam`. Each file gets its own job. Open completed documents to read, compare, edit, highlight, and export. Progress represents completed pipeline stages, not estimated elapsed-time progress.

## Test and convert

```sh
uv run --project backend --extra test python scripts/generate_samples.py
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd frontend
npm test
npm run build
npm run test:e2e # backend and frontend must already be running
cd ..
backend/.venv/bin/python scripts/convert.py samples/digital-english.pdf --engine LIGHTWEIGHT
backend/.venv/bin/python scripts/convert.py my-book.pdf --engine AUTO --languages eng+tam
```

The batch CLI saves a complete ZIP per successful job. The Export tab also offers HTML, AST JSON, assets and diagnostics. Unzip and open `document.html` for semantic content or `reader.html` for the offline Reader API. Copy `reader/examples/DocumentReader.tsx` into a React Native app with `react-native-webview`; see [REACT_NATIVE_WEBVIEW.md](REACT_NATIVE_WEBVIEW.md). Native device behavior remains unverified.

## Documentation

[Architecture](ARCHITECTURE.md) · [Installation](INSTALLATION.md) · [API](API.md) · [Conversion](PDF_CONVERSION.md) · [OCR](MULTILINGUAL_OCR.md) · [HTML](HTML_OUTPUT.md) · [Highlights](HIGHLIGHT_SYSTEM.md) · [Testing](TESTING.md) · [Performance](PERFORMANCE.md) · [Licenses](LICENSES.md) · [Troubleshooting](TROUBLESHOOTING.md) · [Open-source evaluation](docs/OPEN_SOURCE_EVALUATION.md)
