"use strict";
// Capture the browser install event before the page UI is initialized.
window.HscopeInstallState = {prompt: null, installed: false};
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  window.HscopeInstallState.prompt = event;
});
window.addEventListener('appinstalled', () => {
  window.HscopeInstallState.prompt = null;
  window.HscopeInstallState.installed = true;
});
