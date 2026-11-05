# Conversion

PDFInspectionService validates encryption and page count and records dimensions, orientation, suspicious Unicode, CID placeholders, repetition, image coverage and glyph coverage. Classification is heuristic and always carries uncertainty.

AUTO tries available engines sequentially: Marker → Docling → pdfplumber/Tesseract. An explicit engine never silently switches engines. Empty selectable output or a severe measurable text deficit rejects a heavy-engine attempt. Lesser structural concerns remain review warnings. Models unload when their subprocess exits.

The adapters preserve their semantic output through a common block model. Marker uses `PdfConverter`, `create_model_dict` and `HTMLRenderer`, with LLM services disabled. Docling uses `DocumentConverter`, local PDF pipeline options, page-filtered HTML serialization and local picture extraction. Requested Tesseract codes apply to Docling and the lightweight OCR service; Marker uses its own OCR models.

The lightweight converter is a real operational fallback, not a mock: extracts words, font emphasis, heuristic headings and columns, line paragraphs, grid tables, hyperlinks and cropped figures; selectively rasterizes scanned/corrupt pages for Tesseract. It warns about uncertain layout, lists, math, table spans and omitted full-page images. It does not guarantee textbook-quality reconstruction. Native text remains Unicode.

Canonical source-page mappings survive normalization and known-block edits. Unknown mappings remain null. Quality reports count selectable characters, inspected characters, blocks, pages, unmapped blocks and missing assets. No invented accuracy scores. Review the original alongside output before relying on complex equations or tables.
