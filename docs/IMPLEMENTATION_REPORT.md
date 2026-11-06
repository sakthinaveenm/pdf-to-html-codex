# Implementation report

Finalized 2026-11-06. Working APIs, canonical schema and UI were retained while applying the open-source review.

## Delivered

- FastAPI, Pydantic v2, SQLAlchemy/SQLite durable jobs, revisions and annotation CRUD.
- Batch uploads, signature/MIME/size/page validation, isolated processes, cancellation, retries, recovery, timeout and sampled-memory supervision.
- Real Marker primary adapter, modern Docling fallback, and pdfplumber/Tesseract operational fallback; explicit diagnostics and local inference.
- Multilingual configuration, installed pack discovery, UTF-8 content, per-page provenance and RTL attributes.
- Semantic sanitized HTML, canonical typed blocks, stable IDs, local images, quality reports and self-contained ZIP.
- React workspace, real upload progress, stage progress, pagination, PDF.js comparison, TipTap editing, revision conflicts, reader search/font/theme/mobile preview.
- Persistent codepoint/text-quote anchors, conservative recovery, CSS Custom Highlight and text-node fallback, color/delete controls.
- Offline reader bundle and React Native WebView example with versioned bridge.
- Reproducible backend/engine/frontend locks, environment example, startup/conversion scripts, optional API Dockerfile and requested documentation.

## Open-source improvements

Added PDF.js for controlled source preview; reused Docling's page HTML serialization; upgraded Docling/Pillow/Transformers and Vitest after actual audit findings; isolated legacy Marker dependencies; retained TipTap/ProseMirror and the smaller Hypothesis-style annotation adapter. MinerU and pdf2htmlEX were evaluated but not installed without a demonstrated benefit. See OPEN_SOURCE_EVALUATION.md for versions, licenses and decisions.

## Verification

Backend: 18 passed, 2 native-runtime skips. Annotation unit tests: 10 passed. Browser tests: 5 passed. Strict TypeScript/Vite production build passed. Actual CPU conversions completed with Marker 1.9.3 and Docling 2.147.0; scanned/native fallback conversions also completed. Main pip-audit and npm audit reported zero known findings in the captured snapshots; optional legacy Marker findings remain unresolved and documented.

## Remaining requirements

This is a verified local foundation, not an unrestricted production-ready release. Native Android/iOS device testing, GPU/4 GB VRAM benchmarks, representative textbook/layout/math corpus testing, all requested OCR languages, complete lossless editor round trips and hard OS-level sandboxing remain. The API is local and has no multi-user authentication. Source/model license approval and original-code project licensing are still required for commercial distribution. Do not present these gaps as completed.

Installation and execution commands: README.md and INSTALLATION.md. Exact capability reports and quality diagnostics are exposed in the running application. Performance values are measured proof runs, not invented benchmarks.

## Revised primary workflow (2026-11-06)

The workspace is now book/page based, retaining the existing backend and conversion adapters. It shows one original PDF page beside one semantic HTML page, with independent copy, edit/save/reset, retry/reconvert and export. Durable page records expose early completed results, isolate failures and preserve manual corrections. Existing books are indexed using source-page provenance; combined-document revision writes synchronize indexed pages. Book ZIPs contain separate paste/standalone outputs per page, metadata, quality and asset manifests.

Source typography recovery, CropBox coordinate correction and local licensed Unicode fonts address the supplied Hindi cover's flattened headings and duplicate cover image. Actual figures are extracted separately; text remains DOM text. Exact source color/layout reproduction, reliable math/column recovery and OCR accuracy remain incomplete and require review. See TESTING.md for current evidence, docs/PAGE_WORKFLOW.md for use, and docs/OPEN_SOURCE_EVALUATION.md for integration decisions. Native device, UEducate-specific and broad multilingual real-book acceptance are outstanding.
