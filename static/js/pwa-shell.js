"use strict";
(() => {
  const installed = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (!installed) return;
  // Platforms may ignore window resizing or orientation locking; the frame
  // keeps a portrait mobile viewport even when those native requests fail.
  try {
    if (window.matchMedia('(pointer: fine)').matches && window.innerWidth > 520) {
      const chromeWidth = Math.max(0, window.outerWidth - window.innerWidth);
      const chromeHeight = Math.max(0, window.outerHeight - window.innerHeight);
      window.resizeTo(420 + chromeWidth, Math.min(840 + chromeHeight, screen.availHeight));
    }
  } catch (_) {}
  try { screen.orientation?.lock?.('portrait-primary').catch(() => {}); } catch (_) {}
})();
