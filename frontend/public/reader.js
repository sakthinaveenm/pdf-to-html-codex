(() => {
  // ../reader/src/anchors.ts
  var codepoints = (text) => Array.from(text).length;
  function codepointToUtf16(text, offset) {
    const chars = Array.from(text);
    if (offset < 0 || offset > chars.length) throw new RangeError("Codepoint offset outside text");
    return chars.slice(0, offset).join("").length;
  }
  function nodes(root2) {
    const walk = root2.ownerDocument.createTreeWalker(root2, NodeFilter.SHOW_TEXT);
    const found = [];
    while (walk.nextNode()) found.push(walk.currentNode);
    return found;
  }
  function rangeAt(root2, start, end) {
    const list = nodes(root2);
    let cursor = 0;
    let first;
    let last;
    for (const node of list) {
      const size = codepoints(node.data);
      if (!first && start >= cursor && start <= cursor + size) first = [node, codepointToUtf16(node.data, start - cursor)];
      if (end >= cursor && end <= cursor + size) {
        last = [node, codepointToUtf16(node.data, end - cursor)];
        break;
      }
      cursor += size;
    }
    if (!first || !last || end <= start) return null;
    const range = root2.ownerDocument.createRange();
    range.setStart(...first);
    range.setEnd(...last);
    return range;
  }
  function resolveAnchor(annotation, text, revision) {
    const chars = Array.from(text);
    const { start, end } = annotation.position;
    if (annotation.revision === revision && chars.slice(start, end).join("") === annotation.quote.exact) return { ...annotation, status: "resolved" };
    const { exact, prefix, suffix } = annotation.quote;
    const candidates = [];
    let offset = 0;
    while (offset <= text.length) {
      const found = text.indexOf(exact, offset);
      if (found < 0) break;
      if ((!prefix || text.slice(0, found).endsWith(prefix)) && (!suffix || text.slice(found + exact.length).startsWith(suffix))) candidates.push(codepoints(text.slice(0, found)));
      offset = found + Math.max(1, exact.length);
    }
    if (candidates.length !== 1) return { ...annotation, status: "unresolved" };
    return { ...annotation, revision, status: "resolved", position: { start: candidates[0], end: candidates[0] + codepoints(exact), unit: "unicode-codepoint" } };
  }
  function selectionAnchor(root2, documentId, revision) {
    const selection = root2.ownerDocument.getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return null;
    const range = selection.getRangeAt(0);
    if (!root2.contains(range.startContainer) || !root2.contains(range.endContainer)) return null;
    const prefix = root2.ownerDocument.createRange();
    prefix.selectNodeContents(root2);
    prefix.setEnd(range.startContainer, range.startOffset);
    let start = codepoints(prefix.toString());
    let end = start + codepoints(range.toString());
    const text = root2.textContent || "";
    const chars = Array.from(text);
    if ("Segmenter" in Intl) {
      const segmenter = new Intl.Segmenter(void 0, { granularity: "grapheme" });
      const segments = Array.from(segmenter.segment(text));
      const utfStart = codepointToUtf16(text, start), utfEnd = codepointToUtf16(text, end);
      for (const s of segments) {
        if (s.index < utfStart && s.index + s.segment.length > utfStart) start = codepoints(text.slice(0, s.index));
        if (s.index < utfEnd && s.index + s.segment.length > utfEnd) end = codepoints(text.slice(0, s.index + s.segment.length));
      }
    }
    if (end <= start) return null;
    const ids = Array.from(root2.querySelectorAll("[data-block-id]")).filter((n) => range.intersectsNode(n)).map((n) => n.dataset.blockId);
    return { id: crypto.randomUUID(), documentId, revision, blockIds: ids, quote: { exact: chars.slice(start, end).join(""), prefix: chars.slice(Math.max(0, start - 32), start).join(""), suffix: chars.slice(end, end + 32).join("") }, position: { start, end, unit: "unicode-codepoint" }, color: "#ffdf70", status: "resolved" };
  }

  // ../reader/src/index.ts
  var root = document.querySelector("article");
  if (root) {
    let emit = function(type, payload) {
      const msg = { version: 1, type, payload };
      window.ReactNativeWebView?.postMessage(JSON.stringify(msg));
      window.parent.postMessage(msg, window.location.origin === "null" ? "*" : window.location.origin);
    }, clear = function() {
      article.querySelectorAll("mark[data-reader-highlight]").forEach((mark) => mark.replaceWith(...mark.childNodes));
      article.normalize();
      highlights?.clear();
      style.textContent = "";
    }, paint = function() {
      clear();
      const text = article.textContent || "";
      annotations = annotations.map((a) => resolveAnchor(a, text, config.revision));
      const resolved = annotations.filter((a) => a.status === "resolved");
      if (highlights && window.Highlight) {
        resolved.forEach((a, i) => {
          const range = rangeAt(article, a.position.start, a.position.end);
          if (range) {
            const name = "annotation" + i;
            highlights.set(name, new window.Highlight(range));
            style.textContent += `::highlight(${name}){background:${a.color};color:inherit}`;
          }
        });
      } else {
        let cursor = 0;
        const original = nodes(article);
        for (const node of original) {
          const length = codepoints(node.data);
          const relevant = resolved.filter((a) => a.position.start < cursor + length && a.position.end > cursor);
          const boundaries = /* @__PURE__ */ new Set([0, length]);
          relevant.forEach((a) => {
            boundaries.add(Math.max(0, a.position.start - cursor));
            boundaries.add(Math.min(length, a.position.end - cursor));
          });
          const points = Array.from(boundaries).sort((a, b) => a - b);
          const fragment = document.createDocumentFragment();
          for (let i = 0; i < points.length - 1; i++) {
            const from = points[i], to = points[i + 1];
            const textNode = document.createTextNode(node.data.slice(codepointToUtf16(node.data, from), codepointToUtf16(node.data, to)));
            const a = relevant.find((a2) => a2.position.start <= cursor + from && a2.position.end >= cursor + to);
            if (a) {
              const mark = document.createElement("mark");
              mark.dataset.readerHighlight = a.id;
              mark.style.backgroundColor = a.color;
              mark.append(textNode);
              fragment.append(mark);
            } else fragment.append(textNode);
          }
          node.replaceWith(fragment);
          cursor += length;
        }
      }
    }, validate = function(a) {
      return typeof a.id === "string" && typeof a.quote?.exact === "string" && a.quote.exact.length > 0 && /^#[0-9a-fA-F]{6}$/.test(a.color) && Number.isInteger(a.position?.start) && a.position.start >= 0 && Number.isInteger(a.position.end) && a.position.end > a.position.start && a.position.unit === "unicode-codepoint" && Array.isArray(a.blockIds) && a.documentId === config.documentId;
    };
    const article = root;
    const config = window.__readerConfig || { documentId: article.dataset.documentId || "", revision: 1 };
    let annotations = [];
    let pending = null;
    const highlights = CSS.highlights;
    const style = document.createElement("style");
    document.head.append(style);
    window.Reader = {
      restore(items) {
        if (!Array.isArray(items) || items.some((a) => !validate(a))) {
          emit("READER_ERROR", { message: "Invalid annotations" });
          return;
        }
        annotations = items;
        paint();
      },
      selection() {
        return selectionAnchor(article, config.documentId, config.revision) || pending;
      },
      create(color = "#ffdf70") {
        const a = window.Reader.selection();
        if (!a || !/^#[0-9a-fA-F]{6}$/.test(color)) return null;
        a.color = color;
        annotations.push(a);
        paint();
        pending = null;
        emit("HIGHLIGHT_CREATED", { annotation: a });
        return a;
      },
      remove(id) {
        annotations = annotations.filter((a) => a.id !== id);
        paint();
        emit("HIGHLIGHT_REMOVED", { id });
      },
      update(id, color) {
        if (!/^#[0-9a-fA-F]{6}$/.test(color)) return;
        annotations = annotations.map((a) => a.id === id ? { ...a, color } : a);
        paint();
        emit("HIGHLIGHT_UPDATED", { id, color });
      },
      fontSize(size) {
        if (!Number.isFinite(size) || size < 12 || size > 40) return;
        article.style.setProperty("--reader-size", size + "px");
        emit("FONT_SIZE_CHANGED", { size });
      },
      theme(dark) {
        document.body.classList.toggle("dark", dark);
      },
      search(query) {
        paint();
        if (!query) return 0;
        const text = article.textContent || "";
        let from = 0;
        const ranges = [];
        while (from < text.length) {
          const found = text.indexOf(query, from);
          if (found < 0) break;
          const range = rangeAt(article, codepoints(text.slice(0, found)), codepoints(text.slice(0, found + query.length)));
          if (range) ranges.push(range);
          from = found + query.length;
        }
        if (highlights && window.Highlight) {
          highlights.set("search", new window.Highlight(...ranges));
          style.textContent += "::highlight(search){background:#9cdbdf;color:#172226}";
        }
        ranges[0]?.startContainer.parentElement?.scrollIntoView({ block: "center" });
        return ranges.length;
      }
    };
    document.addEventListener("selectionchange", () => {
      const a = selectionAnchor(article, config.documentId, config.revision);
      if (a) {
        pending = a;
        emit("TEXT_SELECTED", { annotation: a, selectedText: a.quote.exact });
      }
    });
    article.addEventListener("click", (event) => {
      const link = event.target.closest("a");
      if (link) {
        event.preventDefault();
        const href = link.getAttribute("href") || "";
        if (/^(https?:|mailto:|#)/.test(href)) emit("LINK_CLICKED", { href });
      }
    });
    if (window.__readerInitialAnnotations) window.Reader.restore(window.__readerInitialAnnotations);
    emit("READER_READY", { documentId: config.documentId, revision: config.revision });
  }
})();
