# UEducate page digitization

1. Start with `./start-macos.command` or `start-windows.cmd`.
2. Upload one or more PDF books. Automatic conversion selects an available engine; conversion settings also permit a chosen engine, OCR languages and font mappings.
3. Choose a book and page in the top toolbar/page grid. The original PDF and generated selectable HTML are displayed together. Ready pages can be reviewed before the entire book finishes.
4. Use **Copy Formatted Content** for normal paste into a rich HTML editor. Use **Copy HTML Source** for a source-code editor. Both operate on the current page only.
5. **Edit HTML** opens TipTap. Save corrections before copying. Corrections are stored locally and independently per page. Reset restores the last generated baseline. Reconvert requires confirmation before replacing saved corrections.
6. Download an independent standalone HTML page, a page ZIP with its snippet/assets/metadata, or a selected/full-book ZIP. Each page folder contains `paste.html` and `standalone.html`.

Images default to self-contained base64. For destination URLs, configure an HTTP(S) asset base URL and upload the assets using the destination filenames in `asset-manifest.json`. The converter does not upload to UEducate itself. Editors can strip base64, inline CSS or font families; validate the pasted result in your destination editor.

Standalone HTML embeds licensed Unicode fonts. Snippets use inline font stacks, so the destination must supply suitable fonts. Native Selection/Range can target DOM text using stable `data-block-id` attributes; scripts are not required to display the content. The existing reader utilities remain available for compatibility testing.

Known limitations: OCR can misread small text and symbols. Legacy font mappings cannot guarantee exact font reuse. Complex columns, colors, formulas and text boxes require manual review. Native mobile engines and UEducate itself have not been verified on devices.

Fallback font sizes are calibrated from source glyph ink with HarfBuzz, rather than assuming a PDF's nominal point size has the same visible size in Noto. For Hindi small print, an optional local higher-accuracy OCR model can retry uncertain lines; install it with `python3 scripts/install_ocr_best.py`. Low-confidence word counts appear in page quality warnings. OCR confidence is not a guarantee that every letter is correct.
