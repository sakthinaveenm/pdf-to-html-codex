# Troubleshooting

- **Backend import or Python version error:** use the locked Python 3.11 backend environment and `PYTHONPATH=backend` from the repository root.
- **No OCR languages / missing pack:** run `tesseract --list-langs`; install the requested code and restart. Check PATH and TESSDATA_PREFIX. Do not treat failed OCR as a successful conversion.
- **First model job is slow:** initial model downloads and loading can take minutes. Inspect storage/tmp/<job-id>.log and the job API. No synthetic elapsed-time progress is shown.
- **Marker missing or incompatible:** configure PDF_MARKER_PYTHON to its isolated interpreter. Read license/audit limitations. Use Docling or LIGHTWEIGHT if the profile is unsuitable.
- **Memory or timeout failure:** lower worker count, use CPU and smaller documents, or use LIGHTWEIGHT. Do not assume CUDA fits 4 GB VRAM.
- **Retry returns 409:** wait for process-tree cleanup after cancellation. Completed jobs cannot be retried through the failed-job endpoint.
- **Document looks reordered or loses formatting:** inspect quality notes and compare pages. Layout detection is imperfect. Try an explicitly selected different converter and correct the output in the editor.
- **Highlight becomes unresolved:** editing made its quote/context absent or ambiguous; recreate the selection. The system deliberately avoids guessing.
- **Offline images fail:** extract the complete ZIP and preserve relative assets paths. A lone HTML download does not bundle images.
- **WebView file loading differs:** follow the upstream local-file guidance and test Android/iOS independently. Browser bridge tests do not prove native filesystem behavior.
- **CORS/origin rejection:** use the documented localhost URLs or update PDF_CORS_ORIGINS and restart. Keep the service bound to loopback.
- **Two servers corrupt job ownership:** use one Uvicorn process per storage directory; configure the internal worker pool instead of Uvicorn --workers.
