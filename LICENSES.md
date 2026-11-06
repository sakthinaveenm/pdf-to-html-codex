# License review

See [third-party inventory](docs/THIRD_PARTY_LICENSES.md) and [version-specific evaluation](docs/OPEN_SOURCE_EVALUATION.md). The application uses open-source components, but that does not imply unrestricted commercial rights for every optional model.

Marker's tested 1.9.3 package declares GPL-3.0-or-later. Its versioned README states separate modified OpenRAIL-M weight terms with a funding/revenue condition. Current upstream has changed source and model terms; those newer statements must not be applied to the installed older release. The isolated profile remains optional and has unresolved security advisories. Review it before use on untrusted PDFs or redistribution.

Docling source is MIT; its model card identifies CDLA-Permissive-2.0 / Apache-2.0 terms. Review actual artifacts. Tesseract engine and official language data use Apache-2.0. No paid API, hosted inference or proprietary OCR dependency is required. Fonts are system fallbacks; no font binaries are distributed.

This repository does not invent a blanket license grant for third-party weights. A project-owner license decision for original application code is still required before presenting a complete commercially distributable release. Preserve dependency LICENSE/NOTICE files and conduct a full distribution review.
