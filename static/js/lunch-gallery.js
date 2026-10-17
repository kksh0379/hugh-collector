/* Verified restaurant photos only. Horizontal snap rail, no auto-playing motion. */
(function (root) {
  "use strict";
  const cache = new Map(), visible = new Set(), attempts = new Map();
  const MAX_ATTEMPTS = 4, REQUEST_TIMEOUT_MS = 12000;
  let observer, timer, busy = false;
  const escape = value => String(value || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function safeUrl(value) {
    try { const u = new URL(value); return /^https?:$/.test(u.protocol) && !u.username && !u.password ? u.href : ""; } catch (_) { return ""; }
  }
  function photoUrls(data) {
    if (data?.status !== "verified" || data.verification !== "business_name_address" || !safeUrl(data.source_url)) return [];
    return [...new Set((data.images || [data.image_url]).map(safeUrl).filter(Boolean))].slice(0, 3);
  }
  function draw(element, data) {
    const urls = photoUrls(data);
    if (!urls.length) {
      element.innerHTML = `<div class="lunch-photo-empty">${data?.status === "pending" ? "매장 사진 다운로드 중…" : data?.status === "search_blocked" ? "확인 가능한 매장 사진이 아직 없어요" : "확인된 매장 사진이 없어요"}</div>`;
      return;
    }
    element.innerHTML = `<div class="lunch-photo-rail" tabindex="0" role="region" aria-label="매장 사진 · 좌우로 넘기기">${urls.map((url, i) => `<img src="${escape(url)}" alt="${escape(element.getAttribute("aria-label"))} ${i + 1}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`).join("")}</div><div class="lunch-photo-caption"><a href="${escape(safeUrl(data.source_url))}" target="_blank" rel="noopener noreferrer">사진 출처 · ${escape(data.source_name)}</a>${urls.length > 1 ? `<span class="lunch-photo-controls"><button type="button" data-photo-step="-1" aria-label="이전 사진">‹</button><span>${urls.length}장 · 좌우로 넘기기</span><button type="button" data-photo-step="1" aria-label="다음 사진">›</button></span>` : ""}</div>`;
    element.querySelectorAll("img").forEach(img => img.addEventListener("error", () => {
      img.hidden = true;
      if (![...element.querySelectorAll("img")].some(item => !item.hidden)) element.innerHTML = '<div class="lunch-photo-empty">사진을 불러올 수 없어요</div>';
    }, {once:true}));
    element.querySelectorAll("[data-photo-step]").forEach(button => button.addEventListener("click", () => {
      const rail = element.querySelector(".lunch-photo-rail");
      rail.scrollBy({left:Number(button.dataset.photoStep) * rail.clientWidth * .85,
        behavior:root.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
    }));
  }
  function schedule(delay = 150) { clearTimeout(timer); timer = setTimeout(refresh, delay); }
  async function refresh() {
    if (busy || document.hidden || document.getElementById("view-food")?.hidden) return;
    const ids = [...visible].filter(id => (!cache.has(id) || cache.get(id).status === "pending") && (attempts.get(id) || 0) < MAX_ATTEMPTS).slice(0,12);
    if (!ids.length) return;
    busy = true;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      let response;
      try { response = await fetch("/api/lunch/images", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ids:ids.map(Number)}), signal:controller.signal}); }
      finally { clearTimeout(timeout); }
      if (!response.ok) throw new Error("Photo lookup unavailable");
      const data = await response.json();
      for (const id of ids) {
        attempts.set(id, (attempts.get(id) || 0) + 1);
        const value = data.images?.[id] || {status:"unverified"};
        if (value.status === "pending" && attempts.get(id) >= MAX_ATTEMPTS) value.status = "timeout";
        cache.set(id, value);
        document.querySelectorAll(`[data-gallery-id="${id}"]`).forEach(element => draw(element,value));
      }
    } catch (_) { ids.forEach(id => { const count = (attempts.get(id) || 0) + 1; attempts.set(id, count); if (count >= MAX_ATTEMPTS) { const value = {status:"timeout"}; cache.set(id,value); document.querySelectorAll(`[data-gallery-id="${id}"]`).forEach(element => draw(element,value)); } }); }
    finally { busy = false; schedule(5000); }
  }
  function mount(list) {
    observer?.disconnect(); visible.clear();
    if (typeof IntersectionObserver !== "undefined") observer = new IntersectionObserver(entries => {
      entries.forEach(entry => { const id = entry.target.dataset.galleryId; if (entry.isIntersecting) visible.add(id); else visible.delete(id); });
      schedule();
    }, {rootMargin:"100px"});
    list.querySelectorAll("[data-gallery-id]").forEach((element, index) => {
      const id = element.dataset.galleryId;
      if (cache.has(id)) draw(element,cache.get(id));
      if (observer) observer.observe(element); else if (index < 12) visible.add(id);
    });
    schedule();
  }
  root.HScopeLunchGallery = {mount};
  if (typeof module !== "undefined") module.exports = {safeUrl,photoUrls};
})(typeof window !== "undefined" ? window : globalThis);
