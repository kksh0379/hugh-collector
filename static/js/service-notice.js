/* One notice per session/day; optional suppression until midnight in Korea. */
(() => {
  const notice = document.getElementById("service-notice");
  if (!notice) return;
  const root = document.documentElement;
  const KEY = "svc-notice-shown";
  const DAY_KEY = "hscopeNoticeHiddenDay";
  const koreaDay = () => new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
  let shownDay = "", hiddenDay = "";
  try {
    shownDay = sessionStorage.getItem(KEY) || "";
    if (shownDay === "1") {
      shownDay = koreaDay();
      sessionStorage.setItem(KEY, shownDay);
    }
  } catch (_) { /* Storage may be unavailable. */ }
  let previousFocus;
  const openNotice = () => {
    const today = koreaDay();
    try { hiddenDay = localStorage.getItem(DAY_KEY) || ""; } catch (_) {}
    if (notice.open || shownDay === today || hiddenDay === today) return;
    previousFocus = document.activeElement;
    notice.showModal();
    shownDay = today;
    try { sessionStorage.setItem(KEY, today); } catch (_) {}
    const checkbox = document.getElementById("service-notice-hide-today");
    if (checkbox) checkbox.checked = false;
    root.classList.add("service-notice-open");
    document.getElementById("service-notice-title").focus();
  };
  document.getElementById("service-notice-form")?.addEventListener("submit", () => {
    if (!document.getElementById("service-notice-hide-today")?.checked) return;
    hiddenDay = koreaDay();
    try { localStorage.setItem(DAY_KEY, hiddenDay); } catch (_) {}
  });
  notice.addEventListener("cancel", event => event.preventDefault());
  notice.addEventListener("close", () => {
    root.classList.remove("service-notice-open");
    if (previousFocus && previousFocus !== document.body && previousFocus.isConnected) {
      previousFocus.focus({preventScroll: true});
    }
  });
  window.addEventListener("pageshow", openNotice);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) openNotice(); });
  openNotice();
})();
