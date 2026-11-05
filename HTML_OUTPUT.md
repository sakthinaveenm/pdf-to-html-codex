# HTML and canonical content

`schemaVersion: 1` canonical documents contain ID, filename, checksum, title, language, revision, pages, typed blocks, assets, metadata and warnings. Each block has a stable ID, type, page, language, direction, semantic content, inline-formatting slot, reading order and provenance. Inline formatting is currently represented in sanitized block HTML; the parallel inlineFormatting array is reserved and empty.

Generated article/sections contain actual text nodes, headings, paragraphs, lists, tables, figures, links, code and allowed MathML. No page canvas/image is used as canonical text. Responsive CSS permits resizing, line reflow, table scrolling, RTL and system-font shaping. Output requires no remote font. Source preview alone uses PDF.js canvas.

nh3 allowlists elements, attributes and safe link schemes. Only registered relative `assets/*.png|jpg|jpeg|webp` images survive; remote, data and traversal image URLs are removed. Scripts, event handlers and arbitrary style attributes are removed. BeautifulSoup parses and normalizes logical blocks. Whitespace and combining marks are preserved.

TipTap maps supported blocks through its schema and carries stable block/page attributes. It may normalize figures, captions and math; explicit warnings describe this. Unrepresentable prior equations/captions are retained in canonical content for review, potentially at the end. Complex nested unsupported structures still need manual verification.

The ZIP bundles HTML, JSON, CSS, local assets, annotations, quality report and reader JS. Paths are relative. `document.html` has no script; `reader.html` enables only the bundled local reader. Standalone HTML downloads refer to relative assets: use the complete ZIP when images are needed offline.
