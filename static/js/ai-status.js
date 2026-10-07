"use strict";

// Background AI analysis also needs a visible credit failure message.
(() => {
  const notice = document.createElement('div');
  notice.className = 'ai-credit-notice';
  notice.setAttribute('role', 'status');
  notice.hidden = true;
  document.body.prepend(notice);
  let busy = false;
  async function refresh() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch('/api/ai/status', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
      if (!response.ok) return;
      const data = await response.json();
      notice.hidden = data.reason !== 'credit_balance';
      if (!notice.hidden && notice.dataset.message !== data.notice) {
        notice.dataset.message = data.notice;
        notice.textContent = data.notice;
      }
    } catch (_) { /* Keep the last known notice during a temporary connection failure. */ }
    finally { busy = false; }
  }
  refresh();
  setInterval(refresh, 15000);
  document.addEventListener('visibilitychange', refresh);
})();
