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

## Single-page/base64 regression checks

Latest run: 21 backend tests passed, 2 native cases skipped; 10 unit tests and 6 browser tests passed. New checks verify a two-page PDF becomes one HTML result with real base64 raster data, images load in the inline TipTap preview, both clipboard formats include the content, images survive edited revisions, unsafe SVG data URLs are rejected, and preview/copy/edit/download plus reader/comparison never change the workspace URL.

## Reported Hindi/image/deletion regressions

Added regression coverage for legacy Indic font detection, known-language override of sparse-page OSD, multiple native scripts in one document, figures retained during forced OCR, a scanned body with only a native footer, document deletion, staging rollback and crash recovery. A local verification of the user-provided 10-page legacy Hindi PDF checked its actual Hindi title/subtitle, recovered Unicode, image decoding in preview and offline HTML, rich clipboard images, and enabled Delete. The private PDF is not included in the repository. Earlier stored conversions are retained; the newest conversion contains the fixes.

Latest verification: 32 backend tests passed, 2 native cases skipped, 8 browser tests passed. Browser verification of the final corrected private PDF additionally checked actual Hindi title text on page 1, Unicode preservation, rendered figures, table nodes, rich clipboard data and offline image loading.

## Page-first acceptance update (2026-11-06)

After the page refactor: backend 35 passed, 2 native-platform checks skipped; frontend Unicode/bridge unit tests 10 passed; Chromium page/compatibility suite 5 passed. Existing backend tests were run before the page changes (32 passed, 2 skipped). Browser coverage now exercises page-only HTML, rich and source clipboard data, actual paste into contenteditable, visible base64 images, TipTap corrections, page isolation, reset, selected exports and deletion. Reader range restoration and simulated WebView bridge tests remain.

Actual `lhac1ps.pdf` (10-page legacy Hindi textbook): all 10 pages converted through lightweight/Tesseract; completed pages were observable while later pages were converting. Visually inspected the original and semantic HTML cover together. Heading hierarchy/size/alignment, QR and logo improved; small-font Hindi OCR remains inaccurate and quality review is required. English samples completed through both installed Marker and Docling using the new page worker. Existing multilingual digital fixtures cover Tamil, Hindi, Telugu, Malayalam, mixed Tamil/English, Arabic and Chinese. These are not substitutes for representative real books across all languages.

Not verified: actual UEducate editor integration, CKEditor, TinyMCE, native Android WebView/iOS WKWebView, Windows launch, a representative engine accuracy benchmark, perfect columns/math/text-box round trips. Browser bridge tests simulate native messaging only. Complex layout/color fidelity remains incomplete; no universal exact-formatting claim is made.

## Alignment/background repair (2026-11-06)

Backend: 37 passed, 2 native checks skipped. Chromium: 6 passed, including equal paper widths, linked scroll positions and resetting scroll on page changes. Graphics regression tests verify that nested PDF Form text operators are removed from the graphics layer while source shapes remain. Sanitization continues to reject absolute positioning on uploaded text; generated decorative image positioning is added only after sanitization.

The saved 10-page Hindi book was repaired without overwriting manual corrections. Pages 1–5 were rendered and visually reviewed. Recovery uses native font sizes/spacing, separate flowing columns, native numeric/Latin tokens where reliable, and a source graphics layer that retains panel fills and watermark opacity. The graphics layer can contain outlined lettering in logos and source image pixels; it is not proof that all visible labels are selectable. Main PDF text is emitted as HTML, not a screenshot. OCR errors and fallback-font differences remain, particularly in dense small-print publishing details. Exact pixel fidelity and native mobile acceptance are not asserted.

## Font-size and missing-character follow-up

Added tests for HarfBuzz ink-based Unicode font sizing, PDF floating-point precision that split native phone numbers, and legacy font symbol codes that must not overwrite real Hindi OCR words. Original nominal font sizes and fallback glyph ink sizes are different; layout now calibrates the fallback size and width from source ink boxes. Font measurements and output remain offline.

The higher-accuracy Hindi model is used for uncertain line retries, while system OCR retains whole-page detection coverage. A whole-page best-model experiment omitted content, so that variant was rejected. Candidate retries must improve confidence and retain at least 95% of the previous line's text length. This is a safeguard, not proof of exact OCR transcription. Remaining low-confidence words are explicitly counted and flagged for source comparison. Existing manual corrections remain protected.

Final follow-up checks: source comparison confirmed recovery of `011-26562708`, `©`, and `रिकॉर्डिंग` on page 2. OCR-only paint cleanup removes rules/filled panels on dark-text pages while retaining native text, preventing rules from being recognized as extra characters; pages with light text retain their backgrounds for OCR. Display/export graphics keep their original appearance. The source Hindi model still has uncertain/misread words (including some diacritics); these are flagged rather than claimed perfectly recovered. The full-page best-model detection experiment and broad legacy-codec substitution were rejected to avoid content regressions.

Final result for this follow-up: 41 backend tests passed, 2 native-platform checks skipped; 10 frontend unit tests passed; 7 Chromium tests passed. The new browser case verifies that inline font sizes survive opening and saving in TipTap. Production frontend build passed. Saved book pages were reprocessed with corrections protected; remaining uncertain OCR is explicitly reported.

## Spacing and dropped-word regression (2026-11-06)

Before this change: 41 backend tests passed, 2 native checks skipped. The supplied page-5 screenshot exposed legacy `•` codes used for Hindi glyphs being mistaken for literal list markers. Literal bullet detection now excludes legacy Indic font encodings throughout word rendering and list reconstruction. Tests cover preserving देखते/सीखने/रखा/सकते while retaining actual Times New Roman bullets. Numeric recovery also preserves mixed Hindi tokens, including the source-verified numeric suffix in कोविड-19.

Source line spans now carry measured word spacing and source indents without changing Unicode text. A borderless signature row retains side-by-side fields on ordinary pages and is sized within the page's content margins. Source-verified spaces restore fused dates such as नवंबर 2006. Word spacing is bounded and retained by sanitization and TipTap's TextStyle adapter. Broader OCR transcription accuracy remains subject to the existing quality warnings.
