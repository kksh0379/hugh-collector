"use strict";
// Run in the head so a saved black theme is applied before the first paint.
(() => {
  const root = document.documentElement;
  const key = 'hscopeTheme';
  const icon = dark => '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + (dark
    ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>'
    : '<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>') + '</svg>';
  const isDark = () => root.dataset.theme === 'black';
  function apply(dark, save = false) {
    root.dataset.theme = dark ? 'black' : 'light';
    root.style.colorScheme = dark ? 'dark' : 'light';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = dark ? '#000000' : '#ffffff';
    const reader = document.getElementById('reader-view');
    if (reader) reader.classList.toggle('dark', dark);
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.innerHTML = icon(dark);
      button.setAttribute('aria-label', dark ? '밝은 테마로 전환' : '블랙테마로 전환');
      button.setAttribute('aria-pressed', String(dark));
      button.title = dark ? '밝은 테마로 전환' : '블랙테마로 전환';
    });
    if (save) {
      try { localStorage.setItem(key, dark ? 'black' : 'light'); } catch (_) {}
    }
  }
  let saved = 'light';
  try {
    saved = localStorage.getItem(key) || (localStorage.getItem('readerDark') === '1' ? 'black' : 'light');
  } catch (_) {}
  apply(saved === 'black');
  window.HScopeTheme = { isDark, toggle: () => apply(!isDark(), true) };
  document.addEventListener('DOMContentLoaded', () => {
    apply(isDark());
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.addEventListener('click', window.HScopeTheme.toggle);
    });
  }, { once: true });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.newValue === 'black');
  });
})();
