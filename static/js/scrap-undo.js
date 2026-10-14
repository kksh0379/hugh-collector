/* One short-lived undo action for the most recent removal from the scrap page. */
(() => {
  'use strict';
  let current = null, timer = null, panel = null;
  function clear(key) {
    if (key && current?.key !== key) return;
    clearTimeout(timer); timer = null; current = null;
    panel?.remove(); panel = null;
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
  window.HScopeScrapUndo = {show,clear};
})();
