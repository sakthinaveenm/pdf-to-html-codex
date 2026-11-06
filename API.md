# API v1

Interactive specification: `http://127.0.0.1:8000/docs`. Machine schema: `/openapi.json`. Errors use `{ "error": { "code": 422, "message": "..." } }`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/jobs` | Multipart `files` (1–20), JSON string `options`; independent per-file success/error results |
| GET | `/api/v1/jobs?offset=0&limit=50` | Paginated jobs and full-database status counts |
| GET | `/api/v1/jobs/{id}` | Status, completed-stage progress, inspection, engine and failure |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel queued or active job |
| POST | `/api/v1/jobs/{id}/retry` | Retry failed/canceled job after cleanup |
| GET | `/api/v1/jobs/{id}/original` | Original PDF |
| GET | `/api/v1/documents/{id}` | Latest canonical document |
| GET | `/api/v1/documents/{id}/ast` | Same versioned canonical JSON |
| GET | `/api/v1/documents/{id}/html?fragment=false&standalone=false` | Full semantic HTML or editor fragment; standalone=true embeds base64 images |
| PUT | `/api/v1/documents/{id}/revisions` | `{baseRevision, html}`; stale base returns 409 |
| GET | `/api/v1/documents/{id}/assets/{assetId}` | Registered local raster asset |
| GET | `/api/v1/documents/{id}/quality` | Structural diagnostics |
| POST / GET | `/api/v1/documents/{id}/highlights` | Create / list validated annotations |
| PATCH / DELETE | `/api/v1/documents/{id}/highlights/{highlightId}` | Change color / remove |
| GET | `/api/v1/documents/{id}/export?format=zip` | `zip`, `html`, `json`, `assets`, `quality` |
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/capabilities` | Installed engines, Tesseract languages, GPU detection and settings |

Options: `engine` = AUTO/MARKER/DOCLING/LIGHTWEIGHT; `languages` = Tesseract codes; `force_ocr` = boolean; `language` = BCP47-style tag or `und`; `dpi` = 100–300. Example:

```sh
curl -F 'files=@samples/digital-english.pdf;type=application/pdf' \
  -F 'options={"engine":"LIGHTWEIGHT","languages":["eng","tam"],"language":"ta"}' \
  http://127.0.0.1:8000/api/v1/jobs
curl -o document.zip 'http://127.0.0.1:8000/api/v1/documents/DOCUMENT_ID/export?format=zip'
```

Capability `installed` means the dependency is present, not that all model files have been downloaded or a GPU fits. Persistent job errors distinguish these conditions. Configuration is environment-based and requires restart; there is no runtime worker-settings API.

`GET /documents/{id}/html?fragment=true&standalone=true` returns one copyable HTML fragment containing all pages and embedded base64 images. `export?format=html` downloads one self-contained file named after the PDF. Missing/unregistered assets return 409 rather than silently exporting broken images.

`DELETE /api/v1/documents/{id}` (also `DELETE /api/v1/jobs/{id}`) permanently removes a completed, failed or canceled document, its original PDF, generated files, revisions, highlights and temporary logs. Returns 204, 404 if absent, or 409 while conversion/cleanup is active. Files are staged before the database commit so failed deletions can restore them; interrupted cleanup/recovery is retried at startup.

## Primary book/page workflow

Existing `/documents` endpoints remain compatibility utilities. Upload books through `POST /api/v1/jobs`; use these page APIs for UEducate digitization:

| Method | Path under `/api/v1` | Purpose |
| --- | --- | --- |
| GET | `/books/{id}/pages` | Total, ready/failed counts and independent page status/progress |
| GET | `/books/{id}/pages/{n}` | Page metadata and current AST/revision |
| GET | `/books/{id}/pages/{n}/html` | Editor-ready fragment; `format=standalone` for complete offline HTML |
| PUT | `/books/{id}/pages/{n}/revisions` | Save `{baseRevision, html}`; stale revision returns 409 |
| POST | `/books/{id}/pages/{n}/reset` | Restore converted baseline as a new revision |
| POST | `/books/{id}/pages/{n}/reconvert` | Queue only this page; corrected pages require `{overwriteEdits:true}` |
| GET | `/books/{id}/pages/{n}/export` | `format=html`, `snippet` or `zip` |
| GET | `/books/{id}/export` | Per-page book ZIP; optional `pages=1,2,5` |

Snippet/export requests accept `image_mode=embedded` (default) or `image_mode=url&asset_base_url=https://destination.example/assets/book`. The asset manifest gives destination filenames; upload assets there before pasting URL-based snippets. Standalone HTML always embeds images/fonts. Copy snippets contain no document wrappers, scripts or stylesheet dependency. `Options.font_mapping` maps a detected font name (or `*`) to `serif`, `sans-serif` or `monospace` before conversion.

A book can be `PARTIAL`: successful pages remain usable and failed pages can be retried independently. No converter API automatically uploads content to UEducate.
