# Open-source evaluation and integration decisions

Review performed 2026-11-05; finalized 2026-11-06. This evaluates the existing application rather than replacing its architecture. Public metadata is captured in [upstream-metadata.json](upstream-metadata.json); exact tested packages are in the lockfiles. Repository activity is an indicator, not proof of maintenance quality. No upstream code was copied or repository forked.

## Existing behavior to preserve

Keep versioned REST endpoints, SQLite job/revision/annotation records, canonical schemaVersion 1, deterministic block IDs, per-page provenance, isolated engine processes, batch UI, TipTap components, semantic HTML, offline ZIP format and explicit unresolved anchors. Backend baseline: 18 passing, 2 native-runtime skips. Annotation baseline: 10 passing unit tests. Initial Vitest collection incorrectly included Playwright; separate configuration fixed the runner. Browser tests initially exposed test selection/queue timing issues; these were corrected without weakening output assertions.

## PDF conversion alternatives

| Project / source | Evaluated and tested version | License / model terms | Output, language and hardware | Decision and limitations |
|---|---|---|---|---|
| [Marker](https://github.com/datalab-to/marker/tree/v1.9.3) | 1.9.3 installed API inspection and actual two-page CPU conversion; latest 2.1.0 reviewed, not executed | Tested package metadata: GPL-3.0-or-later. Its README describes modified OpenRAIL-M model terms with a $2M funding/revenue condition. Current upstream source is Apache-2.0 and has different model terms: never apply current terms retrospectively to 1.9.3. | HTML/Markdown/JSON, semantic tables/figures, multilingual model OCR; CPU/GPU, substantial RAM and cold downloads | Preserve primary adapter, explicitly isolate legacy dependencies. Real result verified. Latest engine introduces inference-server prerequisites, so no untested migration. Old Pillow/Transformers advisories remain in optional runtime. Do not call it commercially unrestricted. |
| [Docling](https://github.com/docling-project/docling) | 2.60.1 initial proof; upgraded and tested 2.147.0 with docling-core 2.106.0, Transformers 5.22.1 | MIT source. [Model card](https://huggingface.co/docling-project/docling-models) declares CDLA-Permissive-2.0 / Apache-2.0; review each configured checkpoint separately. | Structured JSON, HTML, Markdown; multilingual Tesseract OCR; local CPU/GPU | Retain fallback and explicit engine choice. Update justified by known advisories in old version. Reuse page-filtered upstream HTML serialization instead of manually implementing item rendering. Actual CPU conversion completed after upgrade. No claim all model/checkpoint combinations were audited. |
| [MinerU](https://github.com/opendatalab/MinerU) | Current README/license/metadata reviewed; no runtime test | Current [license](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md) is Apache-derived with commercial thresholds and online attribution; not plain Apache. Models vary. | Markdown/JSON, layout/formula/OCR capabilities; backend-dependent hardware | Do not install: no demonstrated improvement on this project's corpus, additional model/dependency cost, changed license terms. Reconsider only after a controlled multilingual/layout benchmark. Accuracy and 4 GB VRAM compatibility unverified. |
| [pdf2htmlEX](https://github.com/pdf2htmlEX/pdf2htmlEX) | Repository/license reviewed; not executed | GPLv3+ package; component exceptions | Positioned HTML and font assets; native-text visual fidelity, not semantic reconstruction | Reject as canonical output: fixed positioning conflicts with reflow/editing priority; native build complexity. Optional fidelity tool only if justified later. Last captured upstream push July 2025. |
| [pdfplumber](https://github.com/jsvine/pdfplumber) + [pypdf](https://github.com/py-pdf/pypdf) | 0.11.9 / 6.21.4; multilingual, table and multipage tests | MIT / BSD-3-Clause; no model weights | Unicode native extraction, font/geometry/table information; CPU, no downloads | Preserve reliable low-memory fallback and inspection. Heuristic column/heading inference cannot replace learned layout recovery. Scanned pages delegated to Tesseract. |

Marker and Docling are not loaded together. Heavy jobs share a model lock, and process exit reclaims weights. The base backend no longer inherits Marker's older Pillow constraints. Optional engines have dedicated adapters; no cloud inference or LLM enhancement is enabled. AUTO only runs fallback after failure or a severe measured text deficit, rather than executing both engines for every PDF.

## OCR alternatives and multilingual accuracy

| Option | Tested/reviewed | Licensing and compatibility | Decision |
|---|---|---|---|
| [Tesseract](https://github.com/tesseract-ocr/tesseract), [tessdata](https://github.com/tesseract-ocr/tessdata) | 5.5.4 and Homebrew language data 4.1.0; English/Tamil scan tests | Apache-2.0 engine/data. Local CLI, configurable multiple packs, CPU-friendly. Indic/Arabic packs require LSTM support rather than legacy-only mode. | Keep. Discover installed languages and fail clearly on missing packs. Native text bypasses OCR. No synthetic confidence scores. |
| [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) / [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) | Upstream alternatives reviewed, not benchmarked here | Apache-2.0 data; accuracy/speed tradeoff, installation-dependent | Keep configurable via TESSDATA_PREFIX. Do not change weights silently or claim an accuracy gain without measuring representative scans. |
| [Surya](https://github.com/datalab-to/surya/tree/v0.16.7), via Marker | 0.16.7 installed; real Marker native PDF proof | Separate source and weight terms; greater memory/model cost | Use only behind Marker. Its OCR languages/settings differ from Tesseract. No redundant standalone OCR integration. |

Native Unicode fixture tests cover Tamil, Hindi, Telugu, Malayalam, Tamil/English, Arabic and Chinese. This tests text identity, not typographic shaping or reading-order perfection. Remaining accuracy work: licensed textbook corpus, noisy Indic scans, charts, equations, table spans, and mixed text/image labels. Compare CER/WER and order against human ground truth before choosing different models or promoting Docling to primary.

## Preview and editor alternatives

- [PDF.js](https://github.com/mozilla/pdf.js), pdfjs-dist 6.5.438, Apache-2.0: **integrated** for original-PDF page rendering. Local worker is bundled; no CDN. Replaces the uncontrolled browser PDF iframe with explicit page navigation. Canvas is used only for the source preview; semantic output remains DOM text. Browser proof verifies actual rendered canvas and HTML text.
- [TipTap](https://github.com/ueberdosis/tiptap), 3.32.3, MIT core/extensions: **preserve**. Reuses ProseMirror editing, tables, image nodes, lists, history and formatting. Commercial extensions/services are not installed.
- [ProseMirror](https://prosemirror.net/), prosemirror-view 1.42.9 through TipTap: MIT. Direct integration would duplicate adapter/UI work without demonstrated benefit. Captured legacy GitHub view repository is archived; review package/repository migration before future upgrades. Lockfile versions and browser tests are the compatibility evidence, not a blanket maintenance claim.

## Annotation alternatives

[Hypothesis client](https://github.com/hypothesis/client) source and [anchoring implementation](https://github.com/hypothesis/client/blob/main/src/annotator/anchoring/html.ts) were reviewed. Its license includes BSD-style terms plus subcomponent notices. It combines range, text-position and text-quote selectors, with quote validation. Embedding the full client introduces unrelated UI/service integration and rendered-text/indexing conventions.

**Decision: preserve the small independent adapter.** The app needs explicit codepoint storage, grapheme-safe selection, shared Python validation, mobile bridge messages and conservative ambiguity handling. These are not a drop-in match for a full Hypothesis client. No code copied. Native Selection/Range and CSS Custom Highlight avoid inventing a browser selection engine. Exact-position + exact-quote/context restoration follows the evaluated approach; ambiguous revisions become unresolved rather than fuzzy guesses. Browser tests cover formatting, multiple paragraphs, astral Unicode, Indic text, resizing and reload in both painting paths. Native devices remain unverified.

## HTML and mobile alternatives

[BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) 4.15.0 (MIT), [lxml](https://github.com/lxml/lxml) 6.1.3 (BSD-style) and [nh3](https://github.com/messense/nh3) 0.3.7 (MIT) remain appropriate. BeautifulSoup handles tree normalization, nh3 performs security sanitization; lxml remains available for parser interoperability. A custom regex-only sanitizer would be less reliable. Tests exercise scripts, unsafe URLs, combining marks and table spans.

[react-native-webview](https://github.com/react-native-webview/react-native-webview), MIT: use the established host component through the provided example. No native package is installed in the browser workspace, and no native tested version is asserted. Compare inline HTML versus a private local file directory: files preserve relative assets, while host platform restrictions require device verification. The [upstream guide](https://github.com/react-native-webview/react-native-webview/blob/master/docs/Guide.md) documents local-file caveats. Browser tests validate bridge events, not Android/iOS file loading.

## Security and reproducibility

- npm audit after Vitest 5.1.0 update: zero known findings in captured report.
- Main Python environment after Docling/Pillow/Transformers upgrades: zero known findings in captured pip-audit report.
- Optional legacy Marker environment retains advisories: [python-audit.json](python-audit.json). Isolation limits dependency coupling; it is not an OS security sandbox or a waiver of vulnerabilities.
- Exact graphs: backend/uv.lock, engines/marker/uv.lock, frontend/package-lock.json. Vulnerability feeds change; rerun audit before deployment. Zero known findings does not prove absence of vulnerabilities.
- No paid services, forked engines, remote fonts or cloud OCR. Downloaded weights need separate provenance/license review before redistribution.

## Missing or unverified production requirements

Native Android/iOS validation; GPU/4 GB VRAM benchmarks; broad real-world multilingual accuracy; robust editor round trips for every math/figure variant; hard OS resource isolation; a corpus-based engine quality comparison; all requested languages as scanned fixtures; multi-user authentication; fully streaming upload caps. Existing APIs/UI/formats remain intact. See TESTING.md and IMPLEMENTATION_REPORT.md for exact evidence.

## Page-first requirement update — 2026-11-06

Preserved FastAPI/SQLite, converter adapters, Tesseract, PDF.js, TipTap/ProseMirror, sanitization and annotation test utilities. Added durable page records and revision baselines rather than replacing the architecture. Existing combined HTML APIs remain for compatibility. A reused engine process converts isolated page PDFs with explicit original-page provenance; one page failure does not discard successful pages. Fresh English samples completed through both installed Marker and Docling page workers. The actual 10-page legacy Hindi textbook completed through lightweight/Tesseract, including reviewable partial progress. This is not a comparative accuracy benchmark.

[Pdf2htmlEX](https://github.com/pdf2htmlEX/pdf2htmlEX) remains an evaluated option for precise fixed layout: upstream documents native positioned text and page-loading modes, and GPLv3+ licensing. It was not installed: it does not demonstrate a benefit for the primary flowing editor-snippet format, adds Poppler/FontForge packaging, and cannot repair missing Unicode mappings by geometry alone. Fixed-layout export remains deferred.

[MinerU](https://github.com/opendatalab/MinerU) currently describes its custom Apache-derived MinerU Open Source License, multilingual OCR and several model backends. It remains uninstalled and unbenchmarked; no superiority claim is made. A representative multilingual book corpus and license review are needed before adding a third heavy engine.

Formatting recovery uses pdfplumber source metrics plus Tesseract word/line boxes, not a new OCR engine. Local OFL Noto Serif, Devanagari and Tamil fonts support standalone output. Original PDF font embedding/ToUnicode presence and subset names are inspected; embedded proprietary fonts are not redistributed. Safe mappings are user selectable. Snippets intentionally depend on destination-installed fallback fonts; standalone pages carry font data and full OFL notices. Complex columns, source colors in OCR, equations and exact glyph metrics still require review.

### Alignment/background repair

Reused pypdf content-stream parsing to separate native text drawing from source graphics, including nested Form XObjects; PDFium renders the resulting graphics layer. Tesseract receives a copy with large sparse transparent decorations omitted, avoiding watermark-driven OCR fragments. Original files are unchanged. Source font metrics guide flowing paragraphs and borderless column tables; the existing HTML sanitizer and TipTap adapter retain a bounded layout vocabulary. No additional engine/dependency was installed. This graphics layer retains original opacity/gray panels and prevents black foreground watermark crops. Logo outline lettering and text already baked into figures can remain raster/vector-derived; native main text is emitted separately as DOM text. Broad automatic layout recovery remains heuristic.

### Glyph sizing and missing-character follow-up

FontTools and HarfBuzz (uharfbuzz) now measure actual shaped fallback-font glyph bounds. PDF nominal font em sizes are not treated as equivalent visible sizes across legacy and Unicode fonts. Per-region ink measurements replace the fixed 75% compression. This preserves text as Unicode DOM content; it does not embed the proprietary original font.

A pinned optional `tessdata_best` Hindi model (4.1.0, Apache-2.0) plus 300-DPI page detection and batched 450-DPI small-print line retries improves the local OCR path. Install with `python3 scripts/install_ocr_best.py`; its downloaded model checksum and license are recorded under storage/models/tessdata_best. Other languages retain their available system models. The conversion checks for local models rather than silently downloading them during a request.

Reviewed legacy converters in https://github.com/deepakkamboj/indianlanguageconverter at 12a87e365b0c2ee6e513343c0b740ac6a8c7d6d6. Their nominal Chanakya mapping does not match the ASCII-heavy Walkman variant used by this PDF, and conversion algorithm licensing includes GPLv2. No converter code or table was copied or bundled. Use calibrated fallback shaping and local OCR with source numeric/Latin/symbol recovery instead; reliable general legacy-font decoding remains a separate evaluated requirement.

Spacing follow-up reuses HarfBuzz advance measurements for bounded per-line word spacing, retaining source line breaks and Unicode DOM text. No extra engine was added. The dropped-word issue was an encoding interpretation bug: a legacy font's `•` code is not necessarily a bullet. Only actual Unicode/symbol-font markers now control list generation. TipTap TextStyle preserves the spacing styles during editing.
