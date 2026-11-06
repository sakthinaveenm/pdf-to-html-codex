# Folio — Multilingual PDF to HTML

Convert multilingual PDF books into **one independently accessible HTML page per PDF page**. Review the original PDF on the left and selectable HTML on the right. Navigate pages, copy formatted content or HTML source, edit and save corrections locally, reset or retry one page, and export a page or selected/full-book ZIP. Snippets contain inline CSS and embedded base64 images by default; destination asset URLs are optional. Standalone pages include local Unicode fonts. No paid API is needed; model engines may download weights on first use.

**Status:** working local application; see [TESTING.md](TESTING.md) and [docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) for measured results and unverified areas. This is not a claim of production readiness or universal PDF accuracy.

## Start automatically (macOS and Windows)

The launchers check prerequisites, install missing packages, verify the locked Python environment and frontend build, then start both servers and open the workspace.

**macOS:** double-click `start-macos.command`, or run:

```sh
./start-macos.command
```

**Windows:** double-click `start-windows.cmd`, or run it in PowerShell:

```powershell
.\start-windows.cmd
```

The first run needs internet access and can take several minutes. Homebrew (macOS) or WinGet (Windows) installs missing Node.js 24+ and Tesseract; the system installer may request your password/administrator approval. Python 3.11 is managed through uv. Windows needs WinGet (Microsoft App Installer). Marker is installed in its isolated runtime by default; use --skip-marker or --lightweight to omit it. Docling model weights download when first used.

Keep the launcher window open; press **Ctrl+C** to stop both servers. If this application is already running, it opens the existing workspace. It refuses to terminate unrelated programs occupying ports 8000/5173. Logs are in `.launcher/logs/`.

Optional arguments work with either launcher:

```sh
./start-macos.command --setup-only        # verify/install without starting servers
./start-macos.command --lightweight       # smaller profile without Docling
./start-macos.command --skip-ocr          # digital PDFs only; omit OCR setup
./start-macos.command --languages eng,tam # limit downloaded OCR packs
./start-macos.command --no-browser       # start without opening a browser
```

On Windows replace `./start-macos.command` with `.\start-windows.cmd`. Existing `.env` settings are preserved; a missing `.env` is copied from the example. The default OCR check covers the 19 target languages. Missing packs are installed as app-local `tessdata_fast` 4.1.0 files, and the launcher verifies a real OCR invocation. Do not run two setup-only installers concurrently or change dependency profiles underneath an active server. Windows execution still needs verification on a Windows host; the macOS setup/start/shutdown path has been exercised.

## Install

Python 3.11 and Node 24+ are required. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

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

The base application also runs without Docling: omit `--extra docling`. Digital extraction works with pdfplumber; scanned pages need Tesseract. Marker uses an isolated legacy profile with important license/security constraints; see [INSTALLATION.md](INSTALLATION.md).

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

Choose files or drop up to 20 PDFs. Set document language and Tesseract codes such as `eng+tam`. Each file gets its own job. The completed result appears inline below the upload queue. Use Preview / Copy HTML to switch documents without leaving the page. Copy HTML code pastes into an editor’s source mode; Copy content pastes formatted content and base64 images; Download single HTML file saves the entire result. Every PDF produces its own complete HTML result, including all pages and base64 images. Progress represents completed pipeline stages, not estimated elapsed-time progress.

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

The workspace is a single page. Upload, queue, editable HTML preview, HTML code, copying, downloads, PDF comparison and reader/highlights remain inline. Only API docs open a separate page. Images in the editor use validated base64 data URLs and survive revision saves.

Use Delete beside a document to permanently remove its PDF, converted HTML, images, revisions and highlights. The page asks for confirmation. Cancel active conversions and wait for them to stop before deleting.
