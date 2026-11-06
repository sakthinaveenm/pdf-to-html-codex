# Verification

Baseline before the open-source review: 18 backend tests passed, 2 native-runtime cases skipped; 10 annotation unit tests passed. Vitest's incorrect Playwright collection was fixed by scoping unit tests to `src/**/*.test.ts`.

After integration: backend tests passed (18 passed, 2 skipped), unit tests passed (10), and Playwright passed (5). The browser flow uploads a real PDF, waits for conversion, checks selectable text, creates a highlight, reloads, resizes fonts, opens TipTap, saves a new revision and exposes exports. Other browser cases exercise both annotation painting paths, Unicode across paragraphs, PDF.js page rendering, and WebView bridge events.

Run from the root:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd frontend
npm test
npm run build
npm run test:e2e
```

The API and frontend must run for Playwright. Generate authored English fixtures with `uv run --project backend --extra test python scripts/generate_samples.py`. Multilingual fixture tests use `FONT_PATH` or macOS Arial Unicode; unavailable fonts yield explicit skips. No third-party PDF corpus is silently substituted. Set FONT_PATH to a suitably licensed TrueType font on other systems.

## Evidence and limits

| Requirement | Evidence |
|---|---|
| Digital English, two-file batch | Real API/worker integration with text assertions |
| Tamil, Hindi, Telugu, Malayalam, Tamil/English, Arabic, Chinese | Generated digital PDF extraction identity checks |
| Scanned English and Tamil | Real Tesseract output checked for expected words |
| Tables / large multipage | Generated grid table contains expected cell; inspection of 50-page PDF |
| Corrupt / encrypted | Jobs fail with diagnostic, no simulated success |
| Unsafe HTML / URL injection | Sanitizer assertions |
| Highlights and revisions | CRUD, persistence, conservative re-anchoring and conflict tests |
| Unicode / inline / paragraphs / resize / reload | Unit and Chromium tests, CSS and fallback painting paths |
| Marker / Docling | Actual CPU API conversions, recorded separately from the fast test suite |
| Android / iOS | Two explicit skips: native runtimes unavailable |

Not yet validated against a representative corpus: complex multi-column textbooks, broken font CMaps, advanced table spans, all mathematical notation, every requested scanned language, charts/captions and natural mixed-direction reading order. These are unresolved requirements, not successful tests. Fixtures are not a substitute for human ground truth.

The test suite emits a Starlette/httpx deprecation warning with the current FastAPI dependency graph. It does not affect the observed passing results. Main dependency audit and npm audit snapshots are under docs; the optional legacy environment has separate unresolved findings.
