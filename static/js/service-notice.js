/* Show on every page entry. Confirmation is deliberately never persisted. */
(() => {
  const notice = document.getElementById("service-notice");
  if (!notice) return;
  const root = document.documentElement;
  let previousFocus;
  const openNotice = () => {
    if (notice.open) return;
    previousFocus = document.activeElement;
    notice.showModal();
    root.classList.add("service-notice-open");
    document.getElementById("service-notice-title").focus();
  };
  notice.addEventListener("cancel", event => event.preventDefault());
  notice.addEventListener("close", () => {
    root.classList.remove("service-notice-open");
    if (previousFocus && previousFocus !== document.body && previousFocus.isConnected) {
      previousFocus.focus({preventScroll: true});
    }
  });
  // A browser history restoration also counts as a new entry.
  window.addEventListener("pageshow", openNotice);
  openNotice();
})();
