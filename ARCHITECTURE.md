# Architecture

React/TypeScript → FastAPI `/api/v1` → SQLAlchemy/SQLite WAL → bounded worker pool → isolated converter subprocess → normalization → versioned canonical JSON and semantic HTML → quality checks → revision transaction.

## Preserved boundaries

`backend/app/api` handles HTTP validation. `schemas` defines versioned content and anchors. `services/pdf_inspector` classifies pages using text quality, glyph and image coverage. `services/converters` exposes replaceable Marker, Docling and lightweight adapters. OCR, HTML, annotations, validation and export remain separate services. `workers/queue.py` owns durable state transitions and process supervision. Model runtimes do not load in the API process.

SQLite revisions are authoritative; HTML/JSON files are materialized snapshots. Exports regenerate from the latest database revision. Source checksums and deterministic block IDs preserve provenance. Editing uses optimistic revision checks; missing mappings remain unknown. Unsupported equations/captions omitted by TipTap are retained at the end of the canonical revision with a review warning.

One worker is the default. Increasing `PDF_WORKERS` allows bounded independent jobs; a shared lock prevents simultaneous heavy engines within the server. Cancellation terminates process trees. Timeout and sampled process-tree RSS enforce soft operational limits. Restart returns interrupted jobs to QUEUED. Failed/canceled jobs can be retried after worker cleanup. Exactly one API process must own a storage directory.

## Reader

The reusable TypeScript reader compiles to an offline IIFE. The same bundle runs in an isolated preview iframe and WebView. Canonical text is concatenated block text in reading order, without synthetic separators. Annotations store codepoint positions, exact quote, surrounding context, revision and block IDs. Native Range APIs create selections; CSS Custom Highlight paints them. A text-node-only fallback preserves paragraph structure. No annotation markup is persisted into canonical content.

## Security boundaries and remaining deployment work

Sanitize every converter result and editor save with nh3; permit local raster assets only. Original PDFs are previewed through PDF.js in the web application. Random storage names and database lookups prevent arbitrary filesystem access. Origin checks and restrictive CORS protect the local API. Exported content has a restrictive CSP. Models perform local inference; initial artifact downloads need network access.

This is a local application, not a multi-user server. Before exposure beyond loopback add authentication, rate limiting, a streaming reverse-proxy body limit, OS/container sandboxing, hardened deployment and a dependency/model license review. Process RSS polling is not a hard OS memory sandbox. Filesystem snapshots and database commits are not one atomic cross-resource transaction; the database remains authoritative. No source deletion API is exposed.
