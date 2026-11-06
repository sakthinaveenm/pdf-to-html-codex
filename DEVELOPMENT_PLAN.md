# Implementation plan

Build a local FastAPI/SQLite durable queue, isolated conversion subprocesses, a versioned canonical document model, semantic sanitized HTML, a React/TipTap workspace, and a reusable Unicode-aware reader.

## Phases and acceptance
- [x] Environment and dependency/license review; reproducible dependency locks.
- [x] Validation, inspection, persistent jobs, crash recovery and cancellation.
- [x] Real digital extraction plus optional Marker primary and Docling fallback.
- [x] Tesseract language discovery, selective OCR, per-page provenance.
- [x] Canonical blocks, assets, sanitized HTML, quality report, offline export.
- [x] Dashboard, batch upload, queue, comparison, editor, reader and exports.
- [x] Unicode codepoint anchors, quote recovery, persistent highlights and bridge.
- [x] Integration/unit/browser tests and actual local conversion verification.
- [x] Installation, architecture, capabilities and limitations documentation.

## Decisions
One worker by default. Heavy converters run in separate processes and unload on process exit. SQLite is the durable source of queue state. Canonical JSON is the content source of truth; revisions use optimistic concurrency. AUTO attempts available Marker, then Docling, then an explicitly reported lightweight pdfplumber/Tesseract fallback. No cloud services. HTML sanitization and local-only asset URLs apply to all engines and editor saves. Progress reports completed pipeline stages, never a time-based simulation.

## Acceptance criteria
Backend and frontend start; real multi-file PDF uploads yield independent jobs and selectable semantic HTML; revisions, highlight CRUD/restoration and offline ZIP work. Tests must check real text, sanitization, Unicode offsets, revisions, and queue failures. Hardware/model/native-mobile gaps must be explicitly reported, not represented as verified.

## Remaining acceptance gaps
Native mobile/GPU validation, broad textbook corpus coverage, complete unsupported editor structures, hard sandboxing and commercial distribution review remain open; see docs/IMPLEMENTATION_REPORT.md. Checked phases indicate implementation work delivered, not universal accuracy or production certification.
