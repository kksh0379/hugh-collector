(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const STORE = 'hscope-video-favorites-v2';
  const PROGRESS = 'hscope-video-progress-v1';
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
    for (const item of [...(Array.isArray(saved) ? saved.slice(0,1000) : [])]) {
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
  let allWorks = [], scope = 'all', visibleCount = 40, indexLoading = false, listScroll = 0;
  let progress = {};
  try { progress = JSON.parse(localStorage.getItem(PROGRESS)) || {}; } catch {}
  if (!progress || typeof progress !== 'object' || Array.isArray(progress)) progress = {};
  try { for (const item of mergeLibrary(JSON.parse(localStorage.getItem('hscope-video-library-v1')))) if (!progress[item.id]) progress[item.id] = {series:item.series, episode:item.episode}; } catch {}
  const cache = new Map();
  function save() { try { localStorage.setItem(STORE, JSON.stringify(library)); } catch {} }
  function status(text, detail = false) { const el = $(detail ? 'videos-detail-status' : 'videos-status'); el.textContent = text; el.hidden = !text; }
  function favoriteLabel(item) { return library.some(x => x.id === item.id) ? '내 목록에서 제거' : '내 목록에 추가'; }
  function toggleFavorite(item) {
    if (library.some(x => x.id === item.id)) library = library.filter(x => x.id !== item.id);
    else library.push({...item});
    save(); renderLibrary();
    if (selected) { $('videos-detail-save').textContent = favoriteLabel(selected); $('videos-detail-save').setAttribute('aria-pressed', String(library.some(x => x.id === selected.id))); }
  }
  function showBrowse(restore = true) {
    ++requestVersion; selected = null; catalog = null; stop(); $('videos-detail').hidden = true; $('videos-browse').hidden = false; status('', true);
    if (restore && !$('view-videos').hidden) window.scrollTo({top:listScroll,left:0,behavior:'instant'});
  }
  function detailUrl(id) { const url = new URL(location.href); if (id) url.searchParams.set('video',id); else url.searchParams.delete('video'); return url; }
  function renderLibrary() {
    const query = $('videos-search').value.trim();
    const rows = discoveryRows(library, allWorks, scope, query);
    $('videos-count').textContent = `총 ${rows.length.toLocaleString()}개${query ? ' · 검색 결과' : ''}${indexLoading ? ' · 전체 목록 불러오는 중…' : ''}`;
    $('videos-more').hidden = rows.length <= visibleCount;
    $('videos-library').replaceChildren(...rows.slice(0, visibleCount).map(item => {
      const card = document.createElement('article'); card.className = 'videos-work';
      const b = document.createElement('button'); b.type = 'button'; b.className = 'videos-work-open';
      const image = cache.get(item.id)?.image || item.image || allWorks.find(x => x.id === item.id)?.image;
      if (image) { const img = document.createElement('img'); img.src = image; img.alt = ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.onerror = () => img.remove(); b.append(img); }
      const name = document.createElement('strong'); name.textContent = item.title; b.append(name);
      if (item.description) { const info = document.createElement('small'); info.textContent = item.description; b.append(info); }
      b.onclick = () => selectWork(item);
      const favorite = document.createElement('button'); favorite.type = 'button'; favorite.className = 'videos-save'; favorite.textContent = favoriteLabel(item);
      favorite.setAttribute('aria-pressed', String(library.some(x => x.id === item.id))); favorite.setAttribute('aria-label', `${item.title} ${favoriteLabel(item)}`);
      favorite.onclick = () => toggleFavorite(item);
      card.append(b, favorite); return card;
    }));
    if (!rows.length) { const p = document.createElement('p'); p.className = 'videos-empty'; p.textContent = indexLoading && scope === 'all' ? '전체 작품 목록을 불러오고 있어요…' : scope === 'saved' && !query ? '마음에 드는 작품을 내 목록에 추가해 보세요.' : '검색 결과가 없어요. 다른 제목으로 찾아보세요.'; $('videos-library').append(p); }
  }
  function stop() { $('videos-player').replaceChildren(); const p = document.createElement('p'); p.textContent = '재생을 눌러 선택한 회차를 감상하세요.'; $('videos-player').append(p); $('videos-play').textContent = '재생'; $('videos-play').disabled = false; }
  function revealEpisode() {
    const list = $('videos-episodes'), button = Array.from(list.querySelectorAll('button')).find(b => Number(b.dataset.episode) === selected.episode);
    if (button) list.scrollTop = Math.max(0, button.offsetTop - (list.clientHeight - button.offsetHeight) / 2);
  }
  function chooseEpisode(number) {
    const playing = $('videos-player').querySelector('iframe') !== null;
    selected.episode = number; progress[selected.id] = {series:selected.series, episode:number};
    try { localStorage.setItem(PROGRESS, JSON.stringify(progress)); } catch {}
    const favorite = library.find(x => x.id === selected.id); if (favorite) { favorite.series = selected.series; favorite.episode = number; save(); }
    stop();
    $('videos-selected').textContent = `${number}화`;
    $('videos-jump').value = String(number); $('videos-jump-status').hidden = true;
    $('videos-original').href = watchUrl(selected);
    $('videos-episodes').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.episode) === number)));
    const eps = catalog.series.find(s => s.id === selected.series).episodes, i = eps.indexOf(number);
    $('videos-prev').disabled = i <= 0; $('videos-next').disabled = i < 0 || i >= eps.length-1;
    revealEpisode();
    if (playing) play();
  }
  function renderSeries() {
    const entries = catalog.series.find(s => s.id === selected.series) || catalog.series[0];
    selected.series = entries.id; $('videos-series').value = String(entries.id);
    $('videos-episode-count').textContent = `총 ${entries.episodes.length.toLocaleString()}화`;
    $('videos-episodes').replaceChildren(...entries.episodes.map(ep => {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.episode = String(ep); b.textContent = `${ep}화`; b.onclick = () => chooseEpisode(ep); return b;
    }));
    chooseEpisode(entries.episodes.includes(selected.episode) ? selected.episode : entries.episodes[0]);
  }
  async function selectWork(item, push = true) {
    if (!$('videos-browse').hidden) listScroll = window.scrollY;
    const savedProgress = progress[item.id];
    const resume = savedProgress && parseWatchUrl(watchUrl({...item, ...savedProgress}));
    const version = ++requestVersion; selected = {...item, ...(resume || {})}; catalog = null; stop();
    $('videos-browse').hidden = true; $('videos-detail').hidden = false; $('videos-detail-body').hidden = true;
    $('videos-title').textContent = item.title; $('videos-detail-save').textContent = favoriteLabel(item); $('videos-detail-save').setAttribute('aria-pressed',String(library.some(x => x.id === item.id)));
    status('작품 정보를 불러오고 있어요…', true);
    if (push) history.pushState({...history.state, hscopeVideo:item.id}, '', detailUrl(item.id));
    window.scrollTo({top:0,left:0,behavior:'instant'});
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 35000);
    try {
      let data = cache.get(item.id);
      if (!data) {
        const response = await fetch(`/api/videos/catalog?id=${selected.id}&series=${selected.series}&episode=${selected.episode}`, {signal:controller.signal});
        data = await response.json(); if (!response.ok) throw Error(data.error || '작품 정보를 불러오지 못했어요.');
      }
      if (version !== requestVersion) return;
      catalog = data; cache.set(item.id, data); selected.title = data.title;
      const favorite = library.find(x => x.id === item.id); if (favorite) { favorite.title = data.title; save(); }
      renderLibrary(); $('videos-title').textContent = selected.title;
      $('videos-series').replaceChildren(...data.series.map(s => { const o = document.createElement('option'); o.value = String(s.id); o.textContent = `시리즈 ${s.id}`; return o; }));
      $('videos-detail-body').hidden = false; renderSeries(); status(data.stale ? '원본 연결이 지연되어 저장된 회차 목록을 표시했어요.' : '', true);
    } catch (e) { if (version === requestVersion) status(e.name === 'AbortError' ? '연결이 지연되고 있어요. 뒤로 간 뒤 작품을 다시 선택해 주세요.' : e.message, true); }
    finally { clearTimeout(timer); }
  }
  function play() {
    if (!selected || !catalog) return;
    const frame = document.createElement('iframe'); frame.src = watchUrl(selected); frame.title = `${selected.title} ${selected.episode}화 재생`;
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
    frame.setAttribute('allow', 'fullscreen; autoplay; encrypted-media; picture-in-picture'); frame.allowFullscreen = true;
    frame.referrerPolicy = 'no-referrer'; $('videos-player').replaceChildren(frame);
    $('videos-play').textContent = '다시 불러오기';
  }
  $('videos-jump-form').onsubmit = event => {
    event.preventDefault(); if (!catalog) return;
    const number = Number($('videos-jump').value), eps = catalog.series.find(s => s.id === selected.series).episodes;
    if (!eps.includes(number)) { $('videos-jump-status').textContent = '이 시리즈에 없는 회차예요. 아래 목록에서 선택해 주세요.'; $('videos-jump-status').hidden = false; return; }
    chooseEpisode(number);
  };
  $('videos-detail-save').onclick = () => { if (selected) toggleFavorite(selected); };
  $('videos-back').onclick = () => {
    if (history.state?.hscopeVideo) history.back();
    else { history.replaceState(history.state, '', detailUrl(null)); showBrowse(); }
  };
  window.addEventListener('popstate', () => {
    const id = new URL(location.href).searchParams.get('video');
    if (id && /^[1-9]\d{0,8}$/.test(id)) {
      if (!$('view-videos').hidden) selectWork(allWorks.find(x => x.id === id) || {id,series:1,episode:1,title:`작품 ${id}`}, false);
    } else showBrowse();
  });
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
      const result = await response.json(); const featured = new Map(DEFAULT_LIBRARY.map((x,i) => [x.id,i]));
      allWorks = result.items.sort((a,b) => (featured.get(a.id) ?? 100) - (featured.get(b.id) ?? 100));
    } catch (e) { status(e.message); }
    finally { indexLoading = false; renderLibrary(); }
  }
  $('videos-search').oninput = () => { visibleCount = 40; renderLibrary(); };
  for (const [id, value] of [['videos-all','all'], ['videos-saved','saved']]) $(id).onclick = () => {
    scope = value; visibleCount = 40; $('videos-all').setAttribute('aria-pressed',String(scope === 'all')); $('videos-saved').setAttribute('aria-pressed',String(scope === 'saved')); renderLibrary();
  };
  $('videos-more').onclick = () => { visibleCount += 40; renderLibrary(); };
  window.onShowVideos = () => {
    if (!initialized) { initialized = true; renderLibrary(); }
    if (!allWorks.length && !indexLoading) loadIndex();
    const id = new URL(location.href).searchParams.get('video');
    if (id && /^[1-9]\d{0,8}$/.test(id) && selected?.id !== id) selectWork(allWorks.find(x => x.id === id) || {id,series:1,episode:1,title:`작품 ${id}`}, false);
  };
  window.onHideVideos = () => {
    if (!$('videos-detail').hidden) { history.replaceState(history.state ? {...history.state,hscopeVideo:null} : null, '', detailUrl(null)); showBrowse(false); } else stop();
  };
  if (new URL(location.href).searchParams.has('video') && window.gotoView) window.gotoView('videos');
})();
