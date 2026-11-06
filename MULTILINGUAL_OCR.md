# Multilingual OCR

Language configuration is extensible and independent of document `lang`. Multiple Tesseract packs can be requested per job. Missing packs fail the OCR attempt with installation guidance; success is never fabricated. See `/api/v1/capabilities` for actual installed packs.

| Language | Tesseract code |
|---|---|
| English / Tamil / Hindi | eng / tam / hin |
| Telugu / Malayalam / Kannada | tel / mal / kan |
| Bengali / Marathi / Gujarati | ben / mar / guj |
| Punjabi / Sanskrit | pan / san |
| Arabic / Urdu | ara / urd |
| Chinese simplified / traditional | chi_sim / chi_tra |
| Japanese / Korean | jpn / kor |
| French / German / Spanish | fra / deu / spa |

Native digital text bypasses OCR by default. Scanned/corrupt pages or forced OCR use page-at-a-time rendering and grayscale autocontrast. The lightweight engine uses Tesseract page segmentation mode 3. Per-page metadata records native versus OCR provenance. Mixed pages with existing text may still contain unread image text; inspect them rather than assuming all labels were recognized.

UTF-8 is used for storage and transport. Combining marks, joiners and Unicode punctuation are retained. RTL direction is inferred per block using Unicode bidi categories; `dir=auto` handles mixed-direction content. No Unicode normalization that strips marks is applied. No language/script has guaranteed accuracy.

Generated digital fixtures cover Tamil, Hindi, Telugu, Malayalam, Tamil/English, Arabic and Chinese. Tesseract English/Tamil scan fixtures check expected real words; they do not establish handwriting, complex shaping or textbook accuracy. See TESTING.md for host-specific fixture font requirements. Install commands are in INSTALLATION.md.

Choose `auto` (or `any`) to detect each OCR page’s script using Tesseract OSD and select an installed script/language pack. Low-text or mixed-script pages can be uncertain: the quality report names the bounded fallback and asks for explicit codes if needed. Any valid installed Tesseract code is accepted, including `script/Arabic`; the document language field accepts any language tag or `any`/`auto` for unspecified. This is not a guarantee of equal OCR quality for every language. Marker uses its own multilingual models rather than Tesseract language restrictions.

For legacy encoded Indic fonts, the font identity supplies a stronger OCR language hint than script detection. A Chanakya Hindi cover uses hin+eng instead of a weak visual script guess. Mixed documents retain per-page detection; a document-wide hint is used only when a page is uncertain. This avoids turning Hindi title pages into unrelated-script text.
