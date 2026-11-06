# Performance

Measured locally on the development Mac, CPU only, authored two-page English fixture. These are single cold/warm proof runs, not representative textbook benchmarks or results for the requested Ryzen/RTX hardware.

| Engine | Observed duration | Context |
|---|---|---|
| Marker 1.9.3 | 149.67 s | First run included model downloads |
| Docling 2.60.1 | 141.39 s | Initial proof, model cache population |
| Docling 2.147.0 | 57.90 s | Updated stack; local model initialization/cache state differs |
| Lightweight | approximately 0.6–0.8 s | Authored tiny English fixture, native/scanned examples |

These runs cannot establish comparative engine accuracy or steady-state throughput. Per-document metadata records duration, engine, OCR languages, completion RSS and platform peak RSS when available. GPU peak is null unless measured; no invented GPU figures. Older proof records predate peak-RSS collection.

One worker and CPU mode are defaults. Heavy engines are serialized even if additional lightweight workers are enabled. Model memory is reclaimed through subprocess exit. `PDF_MEMORY_MB` samples the process tree and kills jobs over the configured limit; this is a soft monitor, not a hard OS cap. `PDF_TIMEOUT_SECONDS` includes conversion attempts. Pages are rendered one at a time for lightweight OCR.

Before 16 GB / 4 GB VRAM deployment measure long textbooks, peak process-tree RSS, latency distribution, page count, CER/WER, reading order and model cache behavior. Choose OCR packs and worker count based on those measurements. No GPU fit or safe parallel-model claim is made.
