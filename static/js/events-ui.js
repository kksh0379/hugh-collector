/* Event discovery: compact month/day agenda and preference-driven banner feed. */
(() => {
  const topics = ['IT·기술','AI·데이터','AI 윤리','산업·비즈니스','문화·전시','교육·공익','기타'];
  const esc = value => escapeHtml(String(value || ''));
  const isoToday = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul'}).format(new Date());
  const isoDate = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
  const dayEvents = (list, iso) => list.filter(s => s.start_date && s.start_date <= iso && (s.end_date || s.start_date) >= iso).sort((a,b)=>(b.start_date||'').localeCompare(a.start_date||''));
  function safeLink(value) { try {const u=new URL(value);return /^https?:$/.test(u.protocol)?u.href:'';}catch(_){return ''; } }
  const tagsHtml = s => eventCategories(s).map(t => `<span class="ed-tag">${esc(t)}</span>`).join('');
  function eventCard(s, banner=false) {
    const link=safeLink(s.source_url || s.url);
    const image=safeLink(s.image_url);
    const index=Math.max(0,topics.indexOf(eventCategories(s)[0]));
    if(banner){
      const art=`${image?`<img loading="lazy" src="/api/img?u=${encodeURIComponent(image)}" alt="" onerror="this.remove()">`:''}<span class="ed-banner-category">${esc(eventCategories(s)[0])}</span><h3>${esc(s.title || '행사')}</h3><div class="ed-banner-facts"><span>${esc(eventDateBadge(s))}</span>${eventPlace(s)?`<span>${esc(eventPlace(s))}</span>`:''}</div>${link?'<span class="ed-banner-arrow" aria-hidden="true">↗</span>':''}`;
      return `<li class="ed-card ed-banner">${link?`<a class="ed-art ed-art-${index}" href="${esc(link)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(s.title || '행사')} 원문 보기">${art}</a>`:`<div class="ed-art ed-art-${index}">${art}</div>`}</li>`;
    }
    const key=registerItem({url:s.url,source_url:s.source_url,title:s.title,published_at:s.published_at,author:s.author,content:s.content},'event',link);
    return `<li class="ed-card${readClass(key)}" data-key="${esc(key)}">
      <div class="ed-card-body"><div class="ed-tags">${tagsHtml(s)} ${eventSrcBadge(s)}</div>
      <h3>${esc(s.title || '제목 없음')}</h3>
      <p class="ed-facts">📅 ${esc(eventDateBadge(s))}${eventPlace(s)?`<br>📍 ${esc(eventPlace(s))}`:''}</p>
      ${s.end_date && s.start_date && s.end_date!==s.start_date?'<span class="ed-range">여러 날 진행하는 행사</span>':''}
      <div class="ed-actions">${scrapBtnHtml(key)}${link?`<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">행사 원문 보기 ↗</a>`:''}</div></div></li>`;
  }
  let month=null,selected=null,expanded=false,calendarItems=[];
  function calendar(list) {
    calendarItems=list;
    const today=isoToday();
    if(!month) month=today.slice(0,7);
    const [y,m]=month.split('-').map(Number),last=new Date(y,m,0).getDate();
    const monthList=list.filter(s=>s.start_date && s.start_date<=`${month}-${last}` && (s.end_date||s.start_date)>=`${month}-01`);
    if(!selected || !selected.startsWith(month)) selected=today.startsWith(month)?today:(monthList.map(s=>s.start_date<`${month}-01`?`${month}-01`:s.start_date).sort()[0] || `${month}-01`);
    const counts=Array.from({length:last},(_,i)=>dayEvents(monthList,`${month}-${String(i+1).padStart(2,'0')}`).length);
    const max=Math.max(1,...counts);
    function cell(iso,day,label='') {
      const n=dayEvents(list,iso).length,level=n?Math.ceil(n/max*4):0;
      return `<button type="button" class="ed-day ed-heat-${level}${iso===selected?' selected':''}${iso===today?' today':''}" data-date="${iso}" aria-pressed="${iso===selected}" aria-label="${esc(iso)} 행사 ${n}건"><strong>${day}</strong>${label?`<small>${label}</small>`:''}<span>${n?n+'건':'—'}</span></button>`;
    }
    let grid='';
    if(!expanded){
      for(let i=0;i<new Date(y,m-1,1).getDay();i++)grid+='<span></span>';
      for(let d=1;d<=last;d++)grid+=cell(`${month}-${String(d).padStart(2,'0')}`,d);
    }else{
      const date=new Date(selected+'T12:00:00');date.setDate(date.getDate()-date.getDay());
      for(let i=0;i<7;i++){const iso=isoDate(date);grid+=cell(iso,date.getDate(),['일','월','화','수','목','금','토'][i]);date.setDate(date.getDate()+1);}
    }
    const chosen=dayEvents(list,selected);
    const title=new Intl.DateTimeFormat('ko-KR',{month:'long',day:'numeric',weekday:'long'}).format(new Date(selected+'T12:00:00'));
    const root=document.getElementById('cal-event');
    root.innerHTML=`<div class="ed-cal-head"><button type="button" data-cal="prev" aria-label="이전 달">‹</button><h3>${y}년 ${m}월 <small>${monthList.length}개 행사</small></h3><button type="button" data-cal="next" aria-label="다음 달">›</button><button type="button" data-cal="today">오늘</button></div>
      ${!expanded?'<div class="ed-dows">'+['일','월','화','수','목','금','토'].map(d=>`<span>${d}</span>`).join('')+'</div>':''}
      <div class="ed-month-grid${expanded?' ed-week':''}">${grid}</div>
      ${!expanded?'<p class="ed-hint">진한 색일수록 행사 많음 · 날짜를 누르면 아래에 상세 목록을 보여줘요.</p>':''}
      <div class="ed-agenda-head"><h3>${esc(title)} <small>${chosen.length}개 행사</small></h3><button type="button" data-cal="expand">${expanded?'달력 펼치기 ↓':'목록 크게 보기 ↑'}</button></div>
      <p class="ed-hint">선택한 날짜에 진행 중인 여러 날 행사도 포함해요.</p>
      <ul class="ed-feed">${chosen.length?chosen.map(s=>eventCard(s)).join(''):'<li class="ed-empty">이 날짜에는 선택 분야의 수집 행사가 없어요.</li>'}</ul>
      ${list.some(s=>!s.start_date)?'<p class="ed-hint">일정 미정 행사는 앨범에서 확인할 수 있어요.</p>':''}`;
    root.onclick=e=>{
      const b=e.target.closest('button[data-date],button[data-cal]');if(!b)return;
      if(b.dataset.date){selected=b.dataset.date;month=selected.slice(0,7);}
      if(b.dataset.cal==='expand')expanded=!expanded;
      if(b.dataset.cal==='today'){month=today.slice(0,7);selected=today;}
      if(['prev','next'].includes(b.dataset.cal)){month=isoDate(new Date(y,m-1+(b.dataset.cal==='next'?1:-1),1)).slice(0,7);selected=null;}
      calendar(calendarItems);
      const focus=root.querySelector(b.dataset.date?`[data-date="${selected}"]`:`[data-cal="${b.dataset.cal}"]`);focus?.focus({preventScroll:true});
    };
  }
  let prefs={topics:[],keywords:[]},initialized=false,available=[],result=null,busy=false,requestVersion=0;
  try {const saved=JSON.parse(localStorage.getItem('event-interests')||'null');if(saved&&Array.isArray(saved.topics)&&Array.isArray(saved.keywords))prefs={topics:saved.topics.filter(t=>topics.includes(t)),keywords:saved.keywords.filter(k=>typeof k==='string'&&k.length<=40).slice(0,8)};}catch(_){}
  function persist(){try{localStorage.setItem('event-interests',JSON.stringify(prefs));}catch(_){}}
  function renderResult(){
    const target=document.getElementById('ed-results');if(!target)return;
    const notice=document.getElementById('ed-status');
    if(busy){notice.textContent='추천 불러오는 중…';notice.hidden=false;if(!result)target.innerHTML='';return;}
    if(!result){notice.textContent='';notice.hidden=true;target.innerHTML='';return;}
    notice.textContent=result.ai_error || !result.items?.length ? result.notice||'' : '';notice.hidden=!notice.textContent;notice.dataset.aiError=result.ai_error||'';
    const keys=new Set(available.map(s=>s.url));
    const items=(result.items||[]).filter(s=>keys.has(s.url));
    target.innerHTML=items.length?items.map(s=>eventCard(s,true)).join(''):'<li class="ed-empty">표시할 추천이 없어요. 관심사나 검색어를 바꿔 보세요.</li>';
    document.getElementById('ed-mode').textContent=result.mode==='ai'?'AI 추천':result.mode==='rules'?'관심사 기반 추천':'';
  }
  async function recommend(){
    const version=++requestVersion;busy=true;renderResult();
    const snapshot=JSON.parse(JSON.stringify(prefs));
    try{
      for(let i=0;i<50;i++){
        if(version!==requestVersion)return;
        const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
        let r;try{r=await fetch('/api/events/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(snapshot),signal:controller.signal});}finally{clearTimeout(timer);}
        if(!r.ok)throw Error('추천을 요청하지 못했어요. 잠시 후 다시 시도해 주세요.');
        const data=await r.json();if(version!==requestVersion)return;
        if(data.status==='pending'){await new Promise(resolve=>setTimeout(resolve,1500));continue;}
        result=data;return;
      }
      throw Error('추천이 지연되고 있어요. 잠시 후 다시 추천해 주세요.');
    }catch(e){if(version===requestVersion)result={notice:e.message||'추천을 불러오지 못했어요.',items:[]};}
    finally{if(version===requestVersion){busy=false;renderResult();}}
  }
  function chips(){
    document.getElementById('ed-keywords').innerHTML=prefs.keywords.map((k,i)=>`<button type="button" class="ed-chip selected" data-remove="${i}" aria-label="${esc(k)} 키워드 제거">${esc(k)} ×</button>`).join('');
  }
  function curation(list){
    available=list;
    if(initialized){renderResult();if(activeTab()==='event' && !result && !busy && list.length)recommend();return;}
    initialized=true;
    const root=document.getElementById('event-curation');
    root.innerHTML=`<div class="ed-curation-toolbar"><span id="ed-mode" class="ed-mode"></span><button type="button" id="ed-settings">관심사 설정</button></div><p id="ed-status" role="status" aria-live="polite" hidden></p><ul id="ed-results" class="ed-feed"></ul><dialog id="ed-dialog" aria-labelledby="ed-dialog-title"><section class="ed-preferences"><div class="ed-dialog-head"><h3 id="ed-dialog-title">관심사 설정</h3><button type="button" id="ed-close" aria-label="설정 닫기">×</button></div><p>미선택 시 전체 행사에서 추천해요.</p>
      <fieldset><legend>관심 분야 · 여러 개 선택</legend><div class="ed-topics">${topics.map(t=>`<label><input type="checkbox" value="${esc(t)}" ${prefs.topics.includes(t)?'checked':''}>${esc(t)}</label>`).join('')}</div></fieldset>
      <label for="ed-keyword-input" class="ed-label">관심 키워드</label><div id="ed-keywords" class="ed-chips"></div>
      <form id="ed-keyword-form"><input id="ed-keyword-input" maxlength="40" placeholder="키워드 직접 입력" aria-label="관심 키워드"><button type="submit">추가</button></form>
      <div class="ed-chips ed-suggestions">${['AI 거버넌스','정보보안','생성형 AI','접근성','클라우드','개발자'].map(k=>`<button type="button" class="ed-chip" data-keyword="${esc(k)}">${esc(k)}</button>`).join('')}</div>
      <button type="button" class="ed-primary" id="ed-recommend">적용하고 추천받기</button></section></dialog>`;
    const addKeyword=k=>{k=k.trim();if(!k)return;if(prefs.keywords.length>=8){toast('키워드는 8개까지 선택할 수 있어요.');return;}if(!prefs.keywords.includes(k))prefs.keywords.push(k);persist();chips();};
    root.querySelector('.ed-topics').onchange=()=>{prefs.topics=Array.from(root.querySelectorAll('.ed-topics input:checked')).map(b=>b.value);persist();};
    root.onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.keyword)addKeyword(b.dataset.keyword);if(b.dataset.remove!==undefined){prefs.keywords.splice(+b.dataset.remove,1);persist();chips();}};
    root.querySelector('#ed-keyword-form').onsubmit=e=>{e.preventDefault();const input=root.querySelector('#ed-keyword-input');addKeyword(input.value);input.value='';};
    const dialog=root.querySelector('#ed-dialog');
    root.querySelector('#ed-settings').onclick=()=>dialog.showModal();
    root.querySelector('#ed-close').onclick=()=>dialog.close();
    dialog.onclick=e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}};
    root.querySelector('#ed-recommend').onclick=()=>{dialog.close();recommend();};
    chips();renderResult();if(activeTab()==='event' && list.length)recommend();
  }
  window.EventDiscovery={calendar,curation};
})();
