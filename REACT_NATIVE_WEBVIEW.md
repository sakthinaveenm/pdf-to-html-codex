# React Native WebView

Use `reader/examples/DocumentReader.tsx` inside an existing React Native TypeScript app:

```sh
npm install react-native-webview
# iOS native project, when applicable:
cd ios && pod install && cd ..
```

Extract the complete export ZIP into one app-private directory. Keep `reader.html`, `reader.js` and `assets/` together. Pass its file URI and the containing directory URI to DocumentReader. iOS uses `allowingReadAccessToURL`; Android uses restricted file access. Platform-specific packaging and file-URI behavior must be checked on devices. The upstream WebView guide documents local-file caveats; a vetted in-app local static server is an alternative if the host's file loader fails.

The reusable Reader API exposes `restore`, `create`, `remove`, `update`, `fontSize`, `theme`, `search` and `selection`. Bundle with `cd frontend && npm run build:reader`. It has no remote dependencies. Set `window.__readerConfig={documentId,revision}` before loading the bundle; the exported reader supplies this configuration.

Messages have `{version:1,type,payload}` and are sent via `window.ReactNativeWebView.postMessage(JSON.stringify(message))`. Types include READER_READY, TEXT_SELECTED, HIGHLIGHT_CREATED, HIGHLIGHT_REMOVED, HIGHLIGHT_UPDATED, LINK_CLICKED, FONT_SIZE_CHANGED, READER_ERROR. The shared parser validates version/type/envelope; hosts must validate action payloads before persisting them. The reader validates annotation fields before restoration. Fixed method names and JSON serialization with escaped `<` protect command injection. External links are intercepted and delivered to the host.

READER_READY → host restores saved annotations. TEXT_SELECTED → display selected text and enable highlighting. HIGHLIGHT_CREATED/REMOVED/UPDATED → persist application state. FONT_SIZE_CHANGED → save preference. The example shows search and font controls; call `Reader.remove(id)` or `Reader.update(id,color)` through the same fixed-method approach for full annotation controls.

Chromium tests exercise bridge messages and both painting paths. Android WebView and iOS WKWebView are explicitly unverified: run selection handles, Indic shaping, context menu/copy, reload, font resizing, local images, links, process recreation and offline startup on real devices before release.
