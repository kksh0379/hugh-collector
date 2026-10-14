/* Undo the latest three scrap removals, newest first, within the notice window. */
(() => {
  'use strict';
  let history = [], timer = null, panel = null, expires = 0;
  const restored = new Map();
  function clear(key) {
    if (key) {
      restored.delete(key);
      const remaining = history.filter(action => action.record.key !== key);
      if (remaining.length === history.length) return;
      history = remaining; render(false); return;
    }
    history = []; clearTimeout(timer); timer = null; expires = 0;
    panel?.remove(); panel = null; restored.clear();
  }
  function render(reset = true) {
    clearTimeout(timer); timer = null;
    panel?.remove(); panel = null;
    if (!history.length) { expires = 0; return; }
    if (reset) expires = Date.now()+5000;
    if (Date.now() >= expires) { clear(); return; }
    const notice = document.createElement('div'); panel = notice;
    notice.className = 'scrap-undo';
    notice.setAttribute('role','status'); notice.setAttribute('aria-live','polite');
    const label = document.createElement('span');label.textContent = '스크랩을 취소했어요';
    const button = document.createElement('button');button.type = 'button';button.textContent = `실행 취소 (${history.length})`;
    button.addEventListener('click',() => {
      if (panel !== notice) return;
      if (Date.now() >= expires) { clear(); return; }
      const action = history.pop();
      render(); action.restore(action.record);
    });
    notice.appendChild(label); notice.appendChild(button);
    document.body.appendChild(notice);
    timer = setTimeout(clear,expires-Date.now());
  }
  function show(record, restore) {
    const last = history.at(-1)?.record;
    if (Date.now() >= expires || (last && (last.user !== record.user || last.generation !== record.generation))) clear();
    history = history.filter(action => action.record.key !== record.key);
    history.push({record:{...record,snapshot:JSON.parse(JSON.stringify(record.snapshot))},restore});
    if (history.length > 3) history.shift();
    render();
  }
  function markRestored(key) {
    restored.set(key,{key,start:null,expires:Date.now()+10000});
  }
  function animateRestored(list) {
    if (!restored.size || list.closest('[hidden]')) return;
    const now = Date.now(),cards = Array.from(list.querySelectorAll('.card[data-key]'));
    for (const [key,action] of restored) {
      if (now >= action.expires) { restored.delete(key); continue; }
      const card = cards.find(node => node.dataset.key === key);
      if (!card) continue;
      if (action.start === null) {
        action.start = now; action.expires = now+1000;
        const rect = card.getBoundingClientRect();
        if (rect.bottom < 80 || rect.top > window.innerHeight-110) card.scrollIntoView({behavior:'instant',block:'center'});
      }
      card.style.animationDelay = -(now-action.start)+'ms';
      card.classList.add('scrap-restored');
      setTimeout(() => {
        card.classList.remove('scrap-restored'); card.style.animationDelay = '';
      },action.expires-now);
    }
  }
  window.HScopeScrapUndo = {show,clear,markRestored,animateRestored};
})();
