/* Local-only placeholders: no images, API calls or artificial delay. */
(() => {
  'use strict';
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const bar = (kind='') => `<span class="hs-sk-block hs-sk-${kind || 'line'}"></span>`;
  function html(kind='card', options={}) {
    const types=['card','food','event','video','metrics','reader','report','table'];
    if (!types.includes(kind)) kind='card';
    const tag=options.list?'li':'div';
    const count=Math.min(8,Math.max(1,Number(options.count)||3));
    const label=escape(options.label||'정보를 불러오는 중이에요.');
    return Array.from({length:count},(_,i)=>`<${tag} class="hs-skeleton hs-sk-${kind}"${i===0?' role="status"':''}>${i===0?`<span class="hs-sk-sr">${label}</span>`:''}<div class="hs-sk-visual" aria-hidden="true">${['card','event','video'].includes(kind)?bar('media'):''}<div class="hs-sk-copy">${bar('meta')}${bar('title')}${bar()}${bar('short')}${['reader','report'].includes(kind)?bar()+bar()+bar('short'):''}${['card','food','event'].includes(kind)?`<div class="hs-sk-actions">${bar('button')}${bar('button')}</div>`:''}</div></div></${tag}>`).join('');
  }
  function render(target,kind,options) {
    if (!target) return;
    target.innerHTML=html(kind,{...options,list:target.tagName==='UL'||target.tagName==='OL'});
  }
  window.HScopeSkeleton={html,render};
})();
