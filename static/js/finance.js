/* Finance is lazy loaded independently of news and the database. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const labels = {policy:'세법·보도자료',guide:'회계·세무 가이드',legislation:'입법예고'};
  const modes = {live:'실데이터',demo:'예시 데이터',unconfigured:'연결 준비',unavailable:'일시 중단',loading:'불러오는 중'};
  let data = null, category = 'all', loading = false, dartVersion = 0;
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function link(url, title) {
    try { const u = new URL(url); if (!['https:','http:'].includes(u.protocol)) return esc(title); }
    catch { return esc(title); }
    return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)} ↗</a>`;
  }
  function readerLink(url, title) {
    // 브리핑 기사는 리더(본문 읽기·AI 요약)로 연다. 좌클릭은 리더, 새 탭/보조클릭은 원문.
    try { const u = new URL(url); if (!['https:','http:'].includes(u.protocol)) return esc(title); }
    catch { return esc(title); }
    return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" data-reader>${esc(title)}</a>`;
  }
  async function json(url, options = {}) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {...options, signal:controller.signal});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '요청을 처리하지 못했습니다.');
      return result;
    } finally { clearTimeout(timer); }
  }
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  function renderNews() {
    if (!data) return;
    const query = $('finance-search').value.trim().toLowerCase();
    const rows = data.items.filter(r => (category === 'all' || r.category === category) && `${r.title} ${r.description} ${r.source}`.toLowerCase().includes(query));
    $('finance-news').innerHTML = rows.length ? rows.map(r => `<article class="finance-news-item"><span class="finance-mode">${esc(labels[r.category])}</span><h3>${readerLink(r.url,r.title)}</h3><p>${esc(r.description)}</p><p class="finance-news-meta">${esc(r.source)}${r.pub_date ? ' · '+esc(r.pub_date) : ''}</p><p class="finance-news-actions"><a class="read-action" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-reader>본문 읽기</a></p></article>`).join('') : '<p class="finance-empty">표시할 소식이 없습니다. 검색 조건 또는 아래 출처의 연결 상태를 확인해 주세요.</p>';
  }
  function renderCalendar() {
    const cal = data && data.calendar, list = $('finance-calendar-list');
    if (!list) return;
    const events = cal && Array.isArray(cal.events) ? cal.events : [];
    const days = '일월화수목금토';
    list.innerHTML = events.length ? events.map(e => {
      // Date is already a KST business day from the server; parse its parts so the
      // viewer's timezone never shifts the day or weekday.
      const [y, m, dd] = String(e.date || '').split('-').map(Number);
      const label = (y && m && dd) ? `${m}.${dd}(${days[new Date(Date.UTC(y, m-1, dd)).getUTCDay()]})` : esc(e.date);
      const dday = e.days_left === 0 ? 'D-DAY' : (e.days_left > 0 ? 'D-'+e.days_left : '');
      const shift = e.shifted ? '<span class="finance-calendar-shift">주말 순연</span>' : '';
      return `<li class="finance-calendar-item"><span class="finance-calendar-dday${e.days_left===0?' today':''}">${esc(dday)}</span><div><strong>${esc(label)} · ${esc(e.title)}</strong>${shift}<p>${esc(e.note||'')}</p></div></li>`;
    }).join('') : '<li class="finance-calendar-empty">다가오는 신고·납부 기한이 없습니다.</li>';
    $('finance-calendar-message').textContent = cal ? (cal.message || '') : '';
  }
  function render(result) {
    data = result;
    $('finance-indicators').innerHTML = data.indicators.map(r => {
      let chart = '';
      if (r.history.length > 1) {
        // 값 범위로 정규화해 세로 4~32 영역에 맞춘다(환율처럼 큰 수도 박스를 벗어나지 않게).
        const vals = r.history.map(x => x.value), low = Math.min(...vals), range = Math.max(...vals)-low || 1;
        const points = vals.map((v,i) => `${(i*160/(vals.length-1)).toFixed(1)},${(32-(v-low)/range*28).toFixed(1)}`).join(' ');
        chart = `<svg viewBox="0 0 160 36" role="img" aria-label="${esc(r.name)} 최근 6개월 추이"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="1.5"/></svg><span class="finance-spark-label">최근 6개월 추이</span>`;
      }
      return `<article class="finance-indicator"><span class="finance-mode ${r.mode === 'live' ? 'live' : ''}">${esc(modes[r.mode])}</span><h3>${esc(r.name)}</h3><strong>${r.value == null ? '—' : Number(r.value).toLocaleString('ko-KR',{maximumFractionDigits:2})}</strong><span class="finance-unit">${esc(r.unit)}</span>${chart}<p>${r.date ? esc(r.date)+' 기준' : '실제 시세 아님'}</p><p>${r.change == null ? '비교 데이터 없음' : `직전 관측 대비 ${r.change > 0 ? '+' : ''}${esc(r.change)}${r.unit === '%' ? '%p' : esc(r.unit)}`}</p></article>`;
    }).join('');
    renderCalendar();
    $('finance-sources').innerHTML = data.sources.map(s => `<div class="finance-source">${link(s.url,s.name)}<span class="finance-mode">${esc(modes[s.mode])}${s.mode==='live' ? ' · '+s.count+'건' : ''}</span></div>`).join('');
    const hasDemo = data.indicators.some(r => r.mode==='demo');
    $('finance-status').textContent = data.pending ? '연결 상태를 확인하고 있습니다. 아래 숫자는 화면 예시입니다.' : (hasDemo ? '예시 데이터가 포함되어 있습니다. 실제 시세·판단 근거로 사용할 수 없습니다. ' : '지표별 기준일과 출처별 연결 상태를 확인하세요. ') + (data.fetched_at ? '확인: '+new Date(data.fetched_at).toLocaleString('ko-KR') : '');
    renderNews();
  }
  async function load() {
    if (loading) return;
    loading=true; $('finance-refresh').disabled=true;
    try {
      for (let attempt=0; attempt<12; attempt++) {
        const result=await json('/api/finance/dashboard'); render(result);
        if (!result.pending) return;
        await pause(2000);
      }
      $('finance-status').textContent='연결 확인이 지연되고 있습니다. 잠시 후 새로고침해 주세요. 표시된 숫자는 예시입니다.';
    } catch { $('finance-status').textContent='정보를 불러오지 못했습니다. 새로고침으로 다시 시도해 주세요.'; }
    finally { loading=false; $('finance-refresh').disabled=false; }
  }
  async function loadDart() {
    const version=++dartVersion, code=$('finance-corp-code').value.trim();
    $('finance-dart-status').textContent='공시를 불러오는 중입니다.';
    $('finance-dart-rows').innerHTML='';
    try {
      for(let attempt=0; attempt<8; attempt++) {
        const result=await json('/api/finance/disclosures?corp_code='+encodeURIComponent(code));
        if(version!==dartVersion) return;
        if(result.pending) { await pause(1500); continue; }
        $('finance-dart-status').textContent=result.message || '실데이터 · 최근 공시 '+result.items.length+'건';
        $('finance-dart-rows').innerHTML=result.items.length ? result.items.map(r=>`<tr><td>${esc(r.company)}</td><td>${link(r.url,r.title)}</td><td>${esc(r.date)}</td></tr>`).join('') : '<tr><td colspan="3">표시할 공시가 없습니다.</td></tr>';
        return;
      }
      $('finance-dart-status').textContent='조회가 지연되고 있습니다. 다시 조회해 주세요.';
    } catch(e) { if(version===dartVersion) $('finance-dart-status').textContent=e.name==='AbortError' ? '조회 시간이 초과되었습니다. 다시 시도해 주세요.' : e.message; }
  }
  $('finance-filters').addEventListener('click',event=>{
    const button=event.target.closest('[data-category]'); if(!button) return;
    category=button.dataset.category;
    $('finance-filters').querySelectorAll('button').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});
    renderNews();
  });
  $('finance-search').addEventListener('input',renderNews);
  $('finance-refresh').addEventListener('click',()=>{load();loadDart();});
  $('finance-dart-form').addEventListener('submit',event=>{event.preventDefault();loadDart();});
  $('finance-business-form').addEventListener('submit',async event=>{
    event.preventDefault(); const button=event.currentTarget.querySelector('button'); button.disabled=true;
    $('finance-business-result').textContent='국세청 사업자 상태를 확인하고 있습니다.';
    try {
      const r=await json('/api/finance/business-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({number:$('finance-business-number').value.trim()})});
      $('finance-business-result').textContent=r.mode==='live' ? [r.status,r.tax_type,r.end_date ? '폐업일 '+r.end_date : '',r.checked_at ? '조회 '+new Date(r.checked_at).toLocaleString('ko-KR') : ''].filter(Boolean).join(' · ') : r.message;
    } catch(e) { $('finance-business-result').textContent=e.name==='AbortError' ? '조회 시간이 초과되었습니다. 다시 시도해 주세요.' : e.message; }
    finally {button.disabled=false;}
  });
  window.onShowFinance=()=>{load();loadDart();};
})();
