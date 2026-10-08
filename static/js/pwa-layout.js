"use strict";
(() => {
  // Existing installations may still launch /hscope until their manifest refreshes.
  const installed = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (!installed || window.self !== window.top) return;
  const url = new URL(window.location.href);
  if (url.searchParams.get('app') === '1' || url.searchParams.get('app_frame') === '1') return;
  url.searchParams.set('app', '1');
  window.location.replace(url.href);
})();
