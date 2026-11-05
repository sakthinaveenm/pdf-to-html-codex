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
| GET | `/api/v1/documents/{id}/html?fragment=false` | Full semantic HTML or editor fragment |
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
