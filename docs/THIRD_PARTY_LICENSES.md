# Third-party notices and obligations

This inventory identifies upstream projects used by the application. Dependencies retain their own copyrights. Exact transitive packages are recorded in lockfiles; distribution must include the corresponding full installed LICENSE/NOTICE texts, including bundled PDF.js notices. This document is an attribution index, not a replacement for those texts or a legal opinion.

| Component | Upstream | Terms and obligations |
|---|---|---|
| FastAPI / Pydantic / SQLAlchemy / Alembic / Uvicorn | fastapi/fastapi, pydantic/pydantic, sqlalchemy/sqlalchemy, sqlalchemy/alembic, encode/uvicorn | MIT or BSD-style licenses as distributed; retain notices and disclaimers |
| React / React Router / Axios / Vite / TypeScript | facebook/react, remix-run/react-router, axios/axios, vitejs/vite, microsoft/TypeScript | MIT and Apache-2.0 components; retain copyrights, license text and applicable NOTICE |
| TipTap core and included extensions / ProseMirror | ueberdosis/tiptap, ProseMirror | MIT; no commercial extensions included |
| PDF.js | mozilla/pdf.js | Apache-2.0; retain LICENSE and NOTICE supplied in pdfjs-dist |
| Tesseract / language data | tesseract-ocr/tesseract, tesseract-ocr/tessdata | Apache-2.0; data attribution and full terms apply separately from engine |
| Docling | docling-project/docling | MIT source; model terms are separate |
| Docling model checkpoints | huggingface.co/docling-project/docling-models | Model card lists CDLA-Permissive-2.0 and Apache-2.0; inspect actual downloaded checkpoints and include their terms when redistributing |
| Marker 1.9.3 | datalab-to/marker, tag v1.9.3 | Installed metadata GPL-3.0-or-later; source availability/license obligations require review when distributing combined products |
| Marker/Surya weights | datalab-to/marker and datalab-to/surya versioned documentation | Modified OpenRAIL-M conditions; source license alone does not authorize unrestricted model use. Preserve actual checkpoint terms |
| pdfplumber / pdfminer.six | jsvine/pdfplumber, pdfminer/pdfminer.six | MIT |
| pypdf | py-pdf/pypdf | BSD-3-Clause |
| pypdfium2 / PDFium | pypdfium2-team/pypdfium2, pdfium.googlesource.com | Wrapper and bundled binary have multiple notices; preserve installed distribution's complete licenses |
| BeautifulSoup4 / nh3 / lxml | crummy.com/software/BeautifulSoup, messense/nh3, lxml/lxml | MIT / MIT / BSD-style plus underlying library notices |
| Pillow | python-pillow/Pillow | HPND/Pillow distribution notices |
| PyTorch / Transformers | pytorch/pytorch, huggingface/transformers | BSD-style / Apache-2.0; individual model weights separate |
| pytest / Vitest / Playwright / ReportLab | pytest-dev/pytest, vitest-dev/vitest, microsoft/playwright, reportlab | MIT / MIT / Apache-2.0 / BSD-style |

Hypothesis, MinerU and pdf2htmlEX were evaluated, not bundled or copied. Their license discussion is in OPEN_SOURCE_EVALUATION.md. System fonts are referenced by name; no system font binaries are bundled. Multilingual test fixtures using host fonts are generated temporarily, not redistributed as licensed sample books. The included English sample text is project-authored.

Before commercial distribution produce an SBOM, collect installed license texts, audit model artifacts, review copyleft combination/distribution obligations and repeat vulnerability scans. Subprocess separation is not a legal determination about license compatibility. No commercial-use approval is implied.
