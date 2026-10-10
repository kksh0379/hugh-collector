(() => {
  'use strict';
  const toggle = document.getElementById('admin-controls-toggle');
  const grid = document.getElementById('admin-controls-grid');
  if (!toggle || !grid) return;
  const key = 'hscopeAdminToolsExpanded';
  function render(expanded) {
    toggle.setAttribute('aria-expanded', String(expanded));
    grid.hidden = !expanded;
    toggle.querySelector('.admin-controls-state').textContent = expanded ? '접기' : '펼치기';
  }
  let saved = false;
  try { saved = localStorage.getItem(key) === '1'; } catch (_) {}
  render(saved);
  toggle.addEventListener('click', () => {
    const expanded = toggle.getAttribute('aria-expanded') !== 'true';
    render(expanded);
    try { localStorage.setItem(key, expanded ? '1' : '0'); } catch (_) {}
  });
})();
