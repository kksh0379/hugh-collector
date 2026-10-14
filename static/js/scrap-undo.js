/* One short-lived undo action for the most recent removal from the scrap page. */
(() => {
  'use strict';
  let current = null, timer = null, panel = null;
  let restored = null;
  function clear(key) {
    if (key && current?.key !== key) return;
    clearTimeout(timer); timer = null; current = null;
    panel?.remove(); panel = null;
    restored = null;
  }
  function show(record, restore) {
    clear();
    current = {...record,snapshot:JSON.parse(JSON.stringify(record.snapshot)),expires:Date.now()+5000};
    const action = current;
    panel = document.createElement('div');
    panel.className = 'scrap-undo';
    panel.setAttribute('role','status'); panel.setAttribute('aria-live','polite');
    const label = document.createElement('span');label.textContent = '스크랩을 취소했어요';
    const button = document.createElement('button');button.type = 'button';button.textContent = '실행 취소';
    button.addEventListener('click',() => {
      if (current !== action) return;
      if (Date.now() > action.expires) { clear(); return; }
      clear(); restore(action);
    });
    panel.appendChild(label); panel.appendChild(button);
    document.body.appendChild(panel);
    timer = setTimeout(clear,5000);
  }
  function markRestored(key) {
    restored = {key,start:null,expires:Date.now()+10000};
  }
  function animateRestored(list) {
    if (!restored) return;
    const now = Date.now();
    if (now >= restored.expires) { restored = null; return; }
    if (list.closest('[hidden]')) return;
    const card = Array.from(list.querySelectorAll('.card[data-key]')).find(node => node.dataset.key === restored.key);
    if (!card) return;
    if (restored.start === null) {
      restored.start = now; restored.expires = now+1000;
      const rect = card.getBoundingClientRect();
      if (rect.bottom < 80 || rect.top > window.innerHeight-110) card.scrollIntoView({behavior:'instant',block:'center'});
    }
    card.style.animationDelay = -(now-restored.start)+'ms';
    card.classList.add('scrap-restored');
    setTimeout(() => {
      card.classList.remove('scrap-restored'); card.style.animationDelay = '';
    },restored.expires-now);
  }
  window.HScopeScrapUndo = {show,clear,markRestored,animateRestored};
})();
