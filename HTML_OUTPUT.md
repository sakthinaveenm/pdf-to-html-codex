# HTML and canonical content

`schemaVersion: 1` canonical documents contain ID, filename, checksum, title, language, revision, pages, typed blocks, assets, metadata and warnings. Each block has a stable ID, type, page, language, direction, semantic content, inline-formatting slot, reading order and provenance. Inline formatting is currently represented in sanitized block HTML; the parallel inlineFormatting array is reserved and empty.

Generated article/sections contain actual text nodes, headings, paragraphs, lists, tables, figures, links, code and allowed MathML. No page canvas/image is used as canonical text. Responsive CSS permits resizing, line reflow, table scrolling, RTL and system-font shaping. Output requires no remote font. Source preview alone uses PDF.js canvas.

nh3 allowlists elements, attributes and safe link schemes. Only registered relative `assets/*.png|jpg|jpeg|webp` images survive; remote, data and traversal image URLs are removed. Scripts, event handlers and arbitrary style attributes are removed. BeautifulSoup parses and normalizes logical blocks. Whitespace and combining marks are preserved.

TipTap maps supported blocks through its schema and carries stable block/page attributes. It may normalize figures, captions and math; explicit warnings describe this. Unrepresentable prior equations/captions are retained in canonical content for review, potentially at the end. Complex nested unsupported structures still need manual verification.

The ZIP bundles HTML, JSON, CSS, local assets, annotations, quality report and reader JS. Paths are relative. `document.html` has no script; `reader.html` enables only the bundled local reader. The primary single HTML download embeds every registered raster image as a `data:image/...;base64,...` source. The copyable editor fragment does the same. Neither requires a ZIP or separate image files. Canonical internal HTML and the optional ZIP retain relative assets; untrusted data URLs are not globally enabled in the sanitizer.

The inline editor explicitly accepts base64 raster images. On save, the backend decodes and validates PNG/JPEG/WebP images, rejects SVG and oversized/invalid content, deduplicates known assets and stores safe local raster assets before canonical sanitization. Portable HTML embeds them again. This prevents images from resolving against the wrong UI route or being silently removed by the editor.

## Primary output: one source page

The page API produces a section fragment with inline typography, page provenance and stable block IDs. It includes no html/head/body wrappers, scripts or style elements. Standalone output is generated separately with embedded images and licensed local font data. Book ZIPs preserve the page folder structure; selected exports use explicit page numbers. See [docs/PAGE_WORKFLOW.md](docs/PAGE_WORKFLOW.md) and [API.md](API.md).

Legacy combined-document endpoints remain available, and saved combined-document revisions synchronize indexed page content. Prefer page revision endpoints for independently managed page corrections.
