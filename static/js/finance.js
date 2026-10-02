/* Finance is lazy loaded independently of news and the database. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const labels = {policy:'세법·보도자료',guide:'회계·세무 가이드',legislation:'입법예고'};
  const modes = {live:'실데이터',demo:'예시 데이터',unconfigured:'연결 준비',unavailable:'일시 중단',loading:'불러오는 중'};
  let data = null, category = 'all', loading = false, dartVersion = 0, ncData = null;
  const NC_CODE = '036570';
  const ncPlaceholder = () => ({code:'KRX/'+NC_CODE, name:'(주)엔씨', unit:'원', value:null, change:null, ratio:null, date:null, mode:'loading', history:[], desc:''});
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmtDate = value => {
    const s = String(value ?? '');
    if (/^\d{8}$/.test(s)) return s.slice(0,4)+'.'+s.slice(4,6)+'.'+s.slice(6,8);
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[1]}.${m[2]}.${m[3]}` : s;
  };
  function link(url, title) {
    try { const u = new URL(url); if (!['https:','http:'].includes(u.protocol)) return esc(title); }
    catch { return esc(title); }
    return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)} ↗</a>`;
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
    $('finance-news').innerHTML = rows.length ? rows.map(r => {
      const key = r.url;
      // 메인 뉴스 카드와 동일하게 읽음·스크랩·링크복사를 재사용(전역 헬퍼). 본문은 리더로 연다.
      if (typeof registerItem === 'function') registerItem({url:r.url, source_url:r.url, title:r.title,
        published_at:r.pub_date, author:r.source, content:r.description, category:r.category}, 'finance', r.url);
      const read = (typeof isRead === 'function' && isRead(key)) ? ' is-read' : '';
      const scrap = typeof scrapBtnHtml === 'function' ? scrapBtnHtml(key) : '';
      const copy = typeof copyBtnHtml === 'function' ? copyBtnHtml(r.url) : '';
      const titleLink = `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-reader>${esc(r.title)}</a>`;
      return `<article class="finance-news-item card${read}" data-key="${esc(key)}">${scrap}<span class="finance-mode">${esc(labels[r.category])}</span><h3 class="card-title">${titleLink}</h3><p class="card-summary">${esc(r.description)}</p><p class="finance-news-meta">${esc(r.source)}${r.pub_date ? ' · '+esc(fmtDate(r.pub_date)) : ''}</p><div class="card-actions"><a class="read-action" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-reader>본문 읽기</a>${copy}</div></article>`;
    }).join('') : '<p class="finance-empty">표시할 소식이 없습니다. 검색 조건 또는 아래 출처의 연결 상태를 확인해 주세요.</p>';
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
  function indicatorCardHtml(r) {
    let chart = '';
    if (r.history && r.history.length > 1) {
      // 값 범위로 정규화해 세로 4~32 영역에 맞춘다(환율처럼 큰 수도 박스를 벗어나지 않게).
      const vals = r.history.map(x => x.value), low = Math.min(...vals), range = Math.max(...vals)-low || 1;
      const points = vals.map((v,i) => `${(i*160/(vals.length-1)).toFixed(1)},${(32-(v-low)/range*28).toFixed(1)}`).join(' ');
      chart = `<svg viewBox="0 0 160 36" role="img" aria-label="${esc(r.name)} 최근 6개월 추이"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="1.5"/></svg><span class="finance-spark-label">최근 6개월 추이</span>`;
    }
    const help = r.desc ? `<button type="button" class="finance-help" aria-label="${esc(r.name)} 설명 보기" aria-expanded="false" data-tip="${esc(r.desc)}">?</button>` : '';
    const dateLine = r.date ? esc(fmtDate(r.date))+' 기준' : (r.mode === 'loading' ? '불러오는 중…' : '실제 시세 아님');
    let changeLine;
    if (r.change == null) changeLine = r.mode === 'loading' ? '주가를 불러오고 있습니다.' : '비교 데이터 없음';
    else if (r.ratio != null) changeLine = `전일 종가 대비 ${r.change>0?'+':''}${esc(Number(r.change).toLocaleString('ko-KR'))}원 (${r.ratio>0?'+':''}${esc(r.ratio)}%)`;
    else changeLine = `직전 관측 대비 ${r.change>0?'+':''}${esc(r.change)}${r.unit==='%'?'%p':esc(r.unit)}`;
    const isNc = String(r.code||'').startsWith('KRX');
    const idAttr = isNc ? ' id="finance-nc"' : '';
    const refresh = isNc ? `<button type="button" class="finance-stock-refresh" aria-label="주가 새로고침" title="주가 새로고침">↻</button>` : '';
    return `<article class="finance-indicator"${idAttr}><span class="finance-mode ${r.mode === 'live' ? 'live' : ''}">${esc(modes[r.mode])}</span>${refresh}<h3>${esc(r.name)}${help}</h3><strong>${r.value == null ? '—' : Number(r.value).toLocaleString('ko-KR',{maximumFractionDigits:2})}</strong><span class="finance-unit">${esc(r.unit)}</span>${chart}<p>${dateLine}</p><p>${changeLine}</p></article>`;
  }
  function render(result) {
    data = result;
    // 지표 3종(ECOS) + 엔씨 주가(별도 /stock 로드). 엔씨 카드는 ncData를 사용해 폴링에도 유지.
    $('finance-indicators').innerHTML = data.indicators.map(indicatorCardHtml).join('') + indicatorCardHtml(ncData || ncPlaceholder());
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
  async function loadStock() {
    const spin = add => { const b=document.querySelector('.finance-stock-refresh'); if(b) b.classList.toggle('spin', add); };
    spin(true);
    try {
      for (let attempt=0; attempt<8; attempt++) {
        const result = await json('/api/finance/stock');
        if (!result.pending) { ncData = result; const el=$('finance-nc'); if(el) el.outerHTML = indicatorCardHtml(ncData); return; }
        await pause(1500);
      }
    } catch { /* 실패 시 직전 값 유지 */ }
    finally { spin(false); }
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
        $('finance-dart-rows').innerHTML=result.items.length ? result.items.map(r=>`<tr><td>${esc(r.company)}</td><td>${link(r.url,r.title)}</td><td>${esc(fmtDate(r.date))}</td></tr>`).join('') : '<tr><td colspan="3">표시할 공시가 없습니다.</td></tr>';
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
  function closeTips(){
    document.querySelectorAll('.finance-tip').forEach(t=>t.remove());
    document.querySelectorAll('.finance-help[aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));
  }
  $('finance-indicators').addEventListener('click',event=>{
    if(event.target.closest('.finance-stock-refresh')){ event.preventDefault(); loadStock(); return; }
    const btn=event.target.closest('.finance-help'); if(!btn) return;
    event.preventDefault(); event.stopPropagation();
    const wasOpen=btn.getAttribute('aria-expanded')==='true';
    closeTips();
    if(wasOpen) return;
    const host=$('finance-indicators'), tip=document.createElement('span');
    tip.className='finance-tip'; tip.setAttribute('role','tooltip'); tip.textContent=btn.dataset.tip||'';
    host.appendChild(tip); btn.setAttribute('aria-expanded','true');
    const r=btn.getBoundingClientRect(), hr=host.getBoundingClientRect();
    tip.style.maxWidth=Math.max(180,Math.min(260,host.clientWidth-8))+'px';
    let left=r.left-hr.left+r.width/2-tip.offsetWidth/2;
    left=Math.max(4,Math.min(left,host.clientWidth-tip.offsetWidth-4));
    tip.style.left=left+'px';
    tip.style.top=(r.bottom-hr.top+7)+'px';
    tip.style.setProperty('--arrow',(r.left-hr.left+r.width/2-left)+'px');
  });
  document.addEventListener('click',closeTips);
  $('finance-search').addEventListener('input',renderNews);
  $('finance-refresh').addEventListener('click',()=>{load();loadStock();loadDart();});
  $('finance-dart-form').addEventListener('submit',event=>{event.preventDefault();loadDart();});
  const dartNc=document.getElementById('finance-dart-nc');
  if(dartNc) dartNc.addEventListener('click',()=>{ $('finance-corp-code').value=dartNc.dataset.corp||''; loadDart(); });
  $('finance-business-form').addEventListener('submit',async event=>{
    event.preventDefault(); const button=event.currentTarget.querySelector('button'); button.disabled=true;
    $('finance-business-result').textContent='국세청 사업자 상태를 확인하고 있습니다.';
    try {
      const r=await json('/api/finance/business-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({number:$('finance-business-number').value.trim()})});
      $('finance-business-result').textContent=r.mode==='live' ? [r.status,r.tax_type,r.end_date ? '폐업일 '+r.end_date : '',r.checked_at ? '조회 '+new Date(r.checked_at).toLocaleString('ko-KR') : ''].filter(Boolean).join(' · ') : r.message;
    } catch(e) { $('finance-business-result').textContent=e.name==='AbortError' ? '조회 시간이 초과되었습니다. 다시 시도해 주세요.' : e.message; }
    finally {button.disabled=false;}
  });
  window.onShowFinance=()=>{load();loadStock();loadDart();};
})();
