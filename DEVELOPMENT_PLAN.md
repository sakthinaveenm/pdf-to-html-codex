# Revised plan: UEducate multilingual book digitization

The primary unit is one original PDF page and its own editor-ready HTML snippet. The existing application is retained; combined-document APIs remain compatibility endpoints. No new LMS or annotation platform is being built.

## Priorities and acceptance
- [x] Durable book/page records; page-by-page conversion, independent failures and retries, early review of completed pages.
- [x] A single workspace: book selection and page navigator, original PDF left, current HTML right, copy/edit/reset/download controls.
- [x] Independent page snippets (section + inline CSS, no scripts/head/body/stylesheets) and standalone offline pages.
- [ ] Source-derived typography, safe inline formatting, Unicode fonts/fallbacks, figures, tables and page provenance.
- [x] Page revisions and correction protection; reset to converted baseline and explicit overwrite on reconversion.
- [x] Embedded images or configured destination asset URLs; page/asset manifests.
- [x] Full-book or selected-page ZIP with per-page paste.html, standalone.html, metadata and assets.
- [ ] Compatibility checks in TipTap, contenteditable and source editing; additional editors/native platforms reported accurately.
- [ ] Actual multilingual book and browser verification, documentation and unresolved fidelity limits.

## Preserve

FastAPI routes, upload validation, SQLite durability, isolated conversion processes, converter adapters, PDF.js, OCR language discovery, legacy Indic-font repair, base64 assets, TipTap, the clipboard implementation and stable block IDs. Retain the reader/annotation module as an optional compatibility test utility.

## Architecture decisions

One book job owns durable page records. A model process handles successive page PDFs, reusing loaded models where configuration permits, publishes each completed page atomically, and continues after individual page failures. Fallback engines handle only failed pages. Page corrections are independent revisions; a reconversion does not overwrite an edited page without explicit consent. Existing converted books are indexed into page records using sourcePage mappings and receive page-level layout repair where possible.

Primary page snippets contain inline CSS and safe image references, without converter runtime dependencies. Standalone output may embed licensed Unicode fonts. Exact legacy font reuse is not promised when mappings/licenses are unsuitable. Formatting, text correctness and reading order are evaluated separately.

Implemented typography recovery and local Unicode fonts; exact complex-layout fidelity remains open. Browser TipTap/contenteditable/source checks pass. Native/editor-specific acceptance and a real multilingual corpus benchmark remain pending. See TESTING.md for measured results.
