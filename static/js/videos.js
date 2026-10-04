(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const STORE = 'hscope-video-library-v1';
  function parseWatchUrl(value) {
    try {
      const u = new URL(value), m = u.pathname.match(/^\/watch\/([1-9]\d{0,8})\/a([1-9]\d{0,3})\/k([1-9]\d{0,4})\/?$/);
      if (u.origin !== 'https://linkani.tv' || u.username || u.password || !m) return null;
      return {id:m[1], series:Number(m[2]), episode:Number(m[3])};
    } catch { return null; }
  }
  function watchUrl(item) { return `https://linkani.tv/watch/${item.id}/a${item.series}/k${item.episode}/`; }
  function discoveryRows(saved, works, scope, query) {
    const ids = new Set(saved.map(x => x.id));
    const candidates = scope === 'saved' ? saved : saved.concat(works.filter(x => !ids.has(x.id)));
    if (!query) return candidates;
    const normalize = value => value.toLowerCase().replace(/\s+/g, '');
    const exact = candidates.filter(item => normalize(item.title).includes(normalize(query)));
    return exact.length ? exact : candidates.filter(item => typeof koreanMatchAll === 'function' && koreanMatchAll(item.title, query));
  }
  const DEFAULT_LIBRARY = [
    {id:'19240', series:1, episode:8, title:'강철의 연금술사'},
    {id:'3217', series:1, episode:1, title:'원피스'},
    {id:'21707', series:1, episode:1, title:'나루토'},
    {id:'2010', series:1, episode:1, title:'보루토'},
    {id:'70867', series:1, episode:1, title:'바람의 검심'},
  ];
  function mergeLibrary(saved) {
    const result = [], seen = new Set();
    for (const item of [...(Array.isArray(saved) ? saved.slice(0,100) : []), ...DEFAULT_LIBRARY]) {
      const parsed = item && parseWatchUrl(watchUrl(item));
      if (!parsed || seen.has(parsed.id)) continue;
      seen.add(parsed.id);
      result.push({...parsed, title:String(item.title || `작품 ${parsed.id}`).slice(0,160)});
    }
    return result;
  }
  let library = mergeLibrary(null);
  try {
    library = mergeLibrary(JSON.parse(localStorage.getItem(STORE)));
  } catch {}
  let selected = null, catalog = null, requestVersion = 0, initialized = false;
  let allWorks = [], scope = 'all', visibleCount = 40, indexLoading = false;
  const cache = new Map();
  function save() { try { localStorage.setItem(STORE, JSON.stringify(library)); } catch {} }
  function status(text) { $('videos-status').textContent = text; $('videos-status').hidden = !text; }
  function renderLibrary() {
    const query = $('videos-search').value.trim();
    const rows = discoveryRows(library, allWorks, scope, query);
    $('videos-count').textContent = `총 ${rows.length.toLocaleString()}개${query ? ' · 검색 결과' : ''}${indexLoading ? ' · 전체 목록 불러오는 중…' : ''}`;
    $('videos-more').hidden = rows.length <= visibleCount;
    $('videos-library').replaceChildren(...rows.slice(0, visibleCount).map(item => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'videos-work';
      b.setAttribute('aria-pressed', String(item.id === selected?.id));
      const image = cache.get(item.id)?.image || item.image || allWorks.find(x => x.id === item.id)?.image;
      if (image) { const img = document.createElement('img'); img.src = image; img.alt = ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.onerror = () => img.remove(); b.append(img); }
      const name = document.createElement('strong'); name.textContent = item.title; b.append(name);
      if (item.description) { const info = document.createElement('small'); info.textContent = item.description; b.append(info); }
      b.onclick = () => {
        let saved = library.find(x => x.id === item.id);
        if (!saved) { saved = {...item}; library.push(saved); save(); }
        selectWork(saved);
      }; return b;
    }));
    if (!rows.length) { const p = document.createElement('p'); p.className = 'videos-empty'; p.textContent = '검색 결과가 없어요. 다른 제목으로 찾아보세요.'; $('videos-library').append(p); }
  }
  function stop() { $('videos-player').replaceChildren(); const p = document.createElement('p'); p.textContent = '재생을 눌러 선택한 회차를 감상하세요.'; $('videos-player').append(p); }
  function chooseEpisode(number) {
    selected.episode = number; save(); stop();
    $('videos-selected').textContent = `${selected.title} · ${number}화`;
    $('videos-original').href = watchUrl(selected);
    $('videos-episodes').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.episode) === number)));
    const eps = catalog.series.find(s => s.id === selected.series).episodes, i = eps.indexOf(number);
    $('videos-prev').disabled = i <= 0; $('videos-next').disabled = i < 0 || i >= eps.length-1;
  }
  function renderSeries() {
    const entries = catalog.series.find(s => s.id === selected.series) || catalog.series[0];
    selected.series = entries.id; $('videos-series').value = String(entries.id);
    $('videos-episodes').replaceChildren(...entries.episodes.map(ep => {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.episode = String(ep); b.textContent = `${ep}화`; b.onclick = () => chooseEpisode(ep); return b;
    }));
    chooseEpisode(entries.episodes.includes(selected.episode) ? selected.episode : entries.episodes[0]);
  }
  async function selectWork(item) {
    const version = ++requestVersion; selected = item; catalog = null; stop(); $('videos-detail').hidden = true; renderLibrary(); status('작품 정보를 불러오고 있어요…');
    $('videos-status').scrollIntoView({behavior:'smooth',block:'center'});
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 35000);
    try {
      let data = cache.get(item.id);
      if (!data) {
        const response = await fetch(`/api/videos/catalog?id=${item.id}&series=${item.series}&episode=${item.episode}`, {signal:controller.signal});
        data = await response.json(); if (!response.ok) throw Error(data.error || '작품 정보를 불러오지 못했어요.');
      }
      if (version !== requestVersion) return;
      catalog = data; cache.set(item.id, data); item.title = data.title; save(); renderLibrary();
      $('videos-title').textContent = item.title;
      $('videos-series').replaceChildren(...data.series.map(s => { const o = document.createElement('option'); o.value = String(s.id); o.textContent = `시리즈 ${s.id}`; return o; }));
      $('videos-detail').hidden = false; renderSeries(); status(data.stale ? '원본 연결이 지연되어 저장된 회차 목록을 표시했어요.' : '');
      if (!$('view-videos').hidden) $('videos-detail').scrollIntoView({behavior:'smooth',block:'start'});
    } catch (e) { if (version === requestVersion) status(e.name === 'AbortError' ? '연결이 지연되고 있어요. 작품을 다시 선택해 주세요.' : e.message); }
    finally { clearTimeout(timer); }
  }
  function play() {
    if (!selected || !catalog) return;
    const frame = document.createElement('iframe'); frame.src = watchUrl(selected); frame.title = `${selected.title} ${selected.episode}화 재생`;
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
    frame.setAttribute('allow', 'fullscreen; autoplay; encrypted-media; picture-in-picture'); frame.allowFullscreen = true;
    frame.referrerPolicy = 'no-referrer'; $('videos-player').replaceChildren(frame);
  }
  $('videos-add').onsubmit = e => {
    e.preventDefault(); const parsed = parseWatchUrl($('videos-url').value.trim());
    if (!parsed) { status('linkani.tv의 영상 페이지 주소를 입력해 주세요.'); return; }
    let item = library.find(x => x.id === parsed.id);
    if (item) Object.assign(item, parsed);
    else { item = {...parsed, title:`작품 ${parsed.id}`}; library.push(item); }
    save(); $('videos-url').value = ''; selectWork(item);
  };
  $('videos-series').onchange = () => { if (catalog) { selected.series = Number($('videos-series').value); renderSeries(); } };
  $('videos-play').onclick = play;
  for (const [id, offset] of [['videos-prev', -1], ['videos-next', 1]]) $(id).onclick = () => {
    if (!catalog) return;
    const eps = catalog.series.find(s => s.id === selected.series).episodes, ep = eps[eps.indexOf(selected.episode)+offset];
    if (ep) chooseEpisode(ep);
  };
  async function loadIndex() {
    indexLoading = true; renderLibrary();
    try {
      const response = await fetch('/api/videos/library', {cache:'no-cache'});
      if (!response.ok) throw Error('전체 작품 목록을 불러오지 못했어요. 새로고침 후 다시 시도해 주세요.');
      const result = await response.json(); allWorks = result.items;
    } catch (e) { status(e.message); }
    finally { indexLoading = false; renderLibrary(); }
  }
  $('videos-search').oninput = () => { visibleCount = 40; renderLibrary(); };
  for (const [id, value] of [['videos-all','all'], ['videos-saved','saved']]) $(id).onclick = () => {
    scope = value; visibleCount = 40; $('videos-all').setAttribute('aria-pressed',String(scope === 'all')); $('videos-saved').setAttribute('aria-pressed',String(scope === 'saved')); renderLibrary();
  };
  $('videos-more').onclick = () => { visibleCount += 40; renderLibrary(); };
  window.onShowVideos = () => { if (!initialized) { initialized = true; renderLibrary(); } if (!allWorks.length && !indexLoading) loadIndex(); };
  window.onHideVideos = () => stop();
})();
