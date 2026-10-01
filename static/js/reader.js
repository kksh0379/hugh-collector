"use strict";

// Native modal keeps the feed mounted and its scroll position intact.
(() => {
  const dialog = document.getElementById("reader-view");
  const title = document.getElementById("reader-title");
  const meta = document.getElementById("reader-meta");
  const body = document.getElementById("reader-body");
  const status = document.getElementById("reader-status");
  const source = document.getElementById("reader-source");
  const retry = document.getElementById("reader-retry");
  let controller, trigger, activeUrl, sequence = 0, fontSize = 18, oldOverflow;

  function safeUrl(value) {
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch (_) { return null; }
  }

  async function load(url) {
    if (controller) controller.abort();
    controller = new AbortController();
    const currentController = controller;
    const current = ++sequence;
    body.replaceChildren();
    body.setAttribute("aria-busy", "true");
    status.textContent = "기사 본문을 불러오고 있어요…";
    retry.hidden = true;
    const timer = setTimeout(() => currentController.abort(), 25000);
    try {
      const response = await fetch("/api/reader?url=" + encodeURIComponent(url), { signal: currentController.signal });
      const data = await response.json();
      if (current !== sequence || !dialog.open) return;
      if (!response.ok) throw new Error(data.error || "본문을 불러오지 못했습니다.");
      title.textContent = data.title;
      meta.textContent = [data.author, data.published_at].filter(Boolean).join(" · ");
      source.href = safeUrl(data.url) || url;
      status.textContent = data.mode === "excerpt" ? data.notice : "본문 읽기 · 출처의 텍스트를 읽기 편하게 정리했어요.";
      retry.hidden = data.mode !== "excerpt";
      for (const text of data.paragraphs) {
        const p = document.createElement("p");
        p.textContent = text; // Never execute publisher HTML.
        body.append(p);
      }
    } catch (error) {
      if (current !== sequence || !dialog.open) return;
      status.textContent = error.name === "AbortError"
        ? "본문을 불러오는 데 시간이 걸리고 있어요. 다시 시도하거나 원문을 확인해 주세요."
        : (error instanceof SyntaxError || error instanceof TypeError)
          ? "본문을 불러오지 못했습니다. 다시 시도하거나 원문을 확인해 주세요."
          : error.message;
      retry.hidden = false;
    } finally {
      clearTimeout(timer);
      if (current === sequence) body.setAttribute("aria-busy", "false");
    }
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-reader]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = safeUrl(link.href);
    if (!url) { event.preventDefault(); return; }
    event.preventDefault();
    trigger = link;
    activeUrl = url;
    title.textContent = link.closest(".card")?.querySelector(".card-title")?.textContent || "본문 읽기";
    meta.textContent = new URL(url).hostname;
    source.href = url;
    oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    dialog.scrollTop = 0;
    load(url);
  });
  document.getElementById("reader-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    ++sequence;
    if (controller) controller.abort();
    document.body.style.overflow = oldOverflow || "";
    if (trigger?.isConnected) trigger.focus({ preventScroll: true });
  });
  retry.addEventListener("click", () => load(activeUrl));
  document.querySelectorAll("[data-reader-size]").forEach((button) => button.addEventListener("click", () => {
    fontSize = Math.max(16, Math.min(24, fontSize + Number(button.dataset.readerSize)));
    body.style.fontSize = fontSize + "px";
    document.querySelector('[data-reader-size="-2"]').disabled = fontSize === 16;
    document.querySelector('[data-reader-size="2"]').disabled = fontSize === 24;
  }));
})();
