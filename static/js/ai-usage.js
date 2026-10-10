(() => {
  'use strict';
  const button = document.getElementById('ai-usage-btn');
  if (!button) return;
  const modal = document.createElement('div'); modal.className = 'modal'; modal.hidden = true;
  modal.innerHTML = `<div class="modal-box ai-usage-box" role="dialog" aria-modal="true" aria-labelledby="ai-usage-title"><div class="modal-head"><span id="ai-usage-title">토큰 사용량</span><button type="button" class="modal-close window-close" aria-label="닫기" title="닫기"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div><div class="ai-usage-body"><p class="ai-usage-note">적용 이후 요청부터 기록해요. 비용은 토큰·모델 단가로 계산한 예상 금액(USD)이에요. 재시도·자동 분석도 각각 기록하며 캐시된 결과 재조회는 비용이 없어요.</p><div class="ai-usage-cards"></div><form class="ai-balance-form"><label for="ai-balance">결제 사이트에서 확인한 현재 잔액 (USD)</label><div><input id="ai-balance" name="balance" type="number" min="0" max="1000000" step="0.000001" inputmode="decimal" placeholder="예: 10.50" required><button class="btn-collect" type="submit">잔액 맞추기</button></div></form><p class="ai-balance-note"></p><div class="ai-usage-actions"><button type="button" class="btn-status ai-usage-refresh">새로고침</button><a href="https://platform.claude.com/settings/billing" target="_blank" rel="noopener noreferrer">결제 사이트 열기 ↗</a></div><p role="status" class="ai-usage-status"></p><div class="ai-usage-table-wrap"><table class="ai-usage-table"><thead><tr><th>일시 · 기능</th><th>모델</th><th>입력 / 출력</th><th>캐시 생성 / 읽기</th><th>예상 비용</th></tr></thead><tbody></tbody></table></div></div></div>`;
  document.body.append(modal);
  const q = (s) => modal.querySelector(s);
  const usd = (v) => v == null ? '확인 필요' : '$' + (v / 1000000).toFixed(6);
  const status = q('.ai-usage-status');
  let controller;
  function close() { modal.hidden = true; if (controller) controller.abort(); button.focus(); }
  q('.modal-close').addEventListener('click', close);
  modal.addEventListener('click', e => { if (e.target === modal) close(); });
  modal.addEventListener('keydown', e => {
    if (e.key === 'Escape') close();
    if (e.key === 'Tab') {
      const items = [...modal.querySelectorAll('button,input,a[href]')].filter(x => !x.disabled);
      const first=items[0], last=items[items.length-1];
      if(e.shiftKey && document.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first.focus();}
    }
  });
  function render(data) {
    const cards = q('.ai-usage-cards'); cards.replaceChildren();
    [['오늘 예상 사용', usd(data.today.cost_micro)], ['전체 기록', `${data.totals.requests.toLocaleString()}건 · ${data.totals.tokens.toLocaleString()} 토큰`], ['누적 예상 사용', usd(data.totals.cost_micro)], ['예상 잔액', data.baseline ? usd(data.remaining_micro) : '잔액을 입력해 주세요']].forEach(([label,value]) => {
      const card=document.createElement('div'); const title=document.createElement('span'); title.textContent=label;
      const strong=document.createElement('strong'); strong.textContent=value; card.append(title,strong);cards.append(card);
    });
    q('.ai-balance-note').textContent = data.baseline ? `마지막 잔액 확인: ${new Date(data.baseline.updated_at).toLocaleString('ko-KR')} · 이후 휴스코프 사용 비용만 차감해요. 충전하거나 다른 서비스에서 사용했다면 잔액을 다시 맞춰 주세요.${data.remaining_micro == null ? ' 이후 비용 미확인 요청이 있어 잔액을 추정할 수 없어요.' : ''}` : '실제 잔액을 자동으로 조회하지 않아요. 결제 사이트의 현재 잔액을 입력하면 이후 사용분을 차감해요.';
    const tbody=q('tbody');tbody.replaceChildren();
    data.rows.forEach(r => {
      const tr=document.createElement('tr');
      [new Date(r.created_at).toLocaleString('ko-KR')+'\n'+r.feature, r.model || '모델 미확인', `${r.input_tokens.toLocaleString()} / ${r.output_tokens.toLocaleString()}`, `${r.cache_write_tokens.toLocaleString()} / ${r.cache_read_tokens.toLocaleString()}`, r.status >= 300 ? `실패 (${r.status}) · 비용 미확인` : usd(r.cost_micro)].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});tbody.append(tr);
    });
    status.textContent = data.rows.length ? `최근 ${data.rows.length}건${data.totals.unpriced ? ` · 비용 미확인 ${data.totals.unpriced}건` : ''}` : '아직 기록된 요청이 없어요. AI 기능을 사용하면 여기에 표시돼요.';
  }
  async function load(body) {
    if(controller) controller.abort(); controller=new AbortController();
    status.textContent='불러오는 중…';
    try {
      const response=await fetch('/api/admin/ai-usage', {credentials:'same-origin', signal:controller.signal, ...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
      const data=await response.json(); if(!response.ok) throw Error(data.error || '사용량을 불러올 수 없어요.');
      if(!document.body.classList.contains('is-admin')) { close(); return; }
      render(data);
    } catch(e) { if(e.name!=='AbortError') status.textContent=e.message; }
  }
  button.addEventListener('click',()=>{if(!document.body.classList.contains('is-admin'))return;modal.hidden=false;q('.modal-close').focus();load();});
  q('.ai-usage-refresh').addEventListener('click',()=>load());
  q('form').addEventListener('submit',async e=>{e.preventDefault();const save=q('form button');save.disabled=true;try{await load({balance_usd:q('#ai-balance').value});}finally{save.disabled=false;}});
  new MutationObserver(()=>{if(!document.body.classList.contains('is-admin')&&!modal.hidden){close();q('tbody').replaceChildren();q('.ai-usage-cards').replaceChildren();q('#ai-balance').value='';}}).observe(document.body,{attributes:true,attributeFilter:['class']});
})();
