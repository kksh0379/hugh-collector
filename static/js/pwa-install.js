"use strict";
(() => {
  const serviceUrl = 'https://hscope.onrender.com/hscope';
  const officialHost = window.location.origin === new URL(serviceUrl).origin;
  if (officialHost && 'serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {});
  const button = document.getElementById('app-install');
  const card = document.getElementById('install-card');
  if (!button || !card) return;
  const media = window.matchMedia('(display-mode: standalone)');
  let pending = window.HscopeInstallState?.prompt || null;
  let installed = media.matches || navigator.standalone === true || window.HscopeInstallState?.installed === true;
  let busy = false;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent || '') || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const directInstall = typeof navigator.install === 'function';
  function update() {
    const available = officialHost && (pending || directInstall || ios);
    card.hidden = !installed && !available;
    button.disabled = installed || busy || !available;
    button.textContent = installed ? '설치 완료' : ios && !pending && !directInstall ? '홈 화면에 추가' : '앱 설치';
  }
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    if (officialHost) pending = event;
    update();
  });
  window.addEventListener('appinstalled', () => { installed = true; pending = null; busy = false; update(); });
  media.addEventListener?.('change', event => { installed = event.matches; update(); });
  button.addEventListener('click', async () => {
    if (!officialHost || installed || busy) return;
    if (ios && !pending && !directInstall) { window.location.assign('/hscope/install'); return; }
    if (!pending && !directInstall) return;
    busy = true;
    button.disabled = true;
    try {
      if (pending) {
        const request = pending;
        pending = null;
        if (window.HscopeInstallState) window.HscopeInstallState.prompt = null;
        await request.prompt();
        const choice = await request.userChoice;
        installed = choice.outcome === 'accepted';
      } else {
        // Available only in browsers exposing the Web Install API.
        await navigator.install();
      }
    } catch (_) {
      // Do not replace a browser install request with a site-owned popup.
    } finally { busy = false; update(); }
  });
  update();
})();
