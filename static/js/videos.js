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
  let playerVersion = 0, playbackController = null, hlsPlayer = null, playbackTimer = null, cropObserver = null;
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
    closePicker(false);
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
  function playLabel(label, disabled = false) { $('videos-resume-title').textContent = label; $('videos-play').disabled = disabled; }
  function updateResume() {
    if (!selected) return;
    const seconds = Math.max(0, Math.floor(Number(progress[selected.id]?.seconds) || 0));
    $('videos-resume-info').textContent = `${selected.episode}화${seconds ? ' · ' + Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0') : ''}`;
  }
  let sheetOverflow = '';
  function closePicker(focus = true) {
    const sheet = $('videos-picker'); if (!sheet.open) return;
    sheet.close(); document.documentElement.style.overflow = sheetOverflow;
    $('videos-picker-open').setAttribute('aria-expanded', 'false');
    if (focus) $('videos-picker-open').focus({preventScroll:true});
  }
  function sizePicker() {
    const controls = $('videos-picker-open').getBoundingClientRect();
    const available = (window.visualViewport?.height || window.innerHeight) - Math.max(0, controls.bottom) - 8;
    $('videos-picker').style.setProperty('--sheet-height', `${Math.max(300, Math.min(440, available))}px`);
  }
  function openPicker() {
    if (!catalog || $('videos-picker').open) return;
    sizePicker(); sheetOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    $('videos-picker').showModal(); $('videos-picker-open').setAttribute('aria-expanded', 'true');
    revealEpisode();
  }
  function pickEpisode(number) { closePicker(); chooseEpisode(number, true); }
  $('videos-picker-open').onclick = openPicker;
  $('videos-picker-close').onclick = () => closePicker();
  $('videos-picker').addEventListener('cancel', event => { event.preventDefault(); closePicker(); });
  $('videos-picker').onclick = event => { if (event.target === $('videos-picker')) { const r = $('videos-picker').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closePicker(); } };
  window.addEventListener('resize', () => { if ($('videos-picker').open) { sizePicker(); revealEpisode(); } });
  window.visualViewport?.addEventListener('resize', () => { if ($('videos-picker').open) sizePicker(); });
  function stop() { ++playerVersion; cropObserver?.disconnect(); cropObserver = null; playbackController?.abort(); playbackController = null; clearTimeout(playbackTimer); hlsPlayer?.destroy(); hlsPlayer = null; const video = $('videos-player').querySelector('video'); if (video) { video.pause(); video.removeAttribute('src'); video.load(); } $('videos-player').replaceChildren(); const p = document.createElement('p'); p.textContent = '재생을 눌러 선택한 회차를 감상하세요.'; $('videos-player').append(p); playLabel(selected && Number(progress[selected.id]?.seconds) > 0 ? '이어보기' : '재생하기'); }
  function revealEpisode() {
    const list = $('videos-episodes'), button = Array.from(list.querySelectorAll('button')).find(b => Number(b.dataset.episode) === selected.episode);
    if (button) list.scrollTop = Math.max(0, button.offsetTop - (list.clientHeight - button.offsetHeight) / 2);
  }
  function chooseEpisode(number, autoplay = false) {
    const playing = !!$('videos-player').querySelector('iframe, video') || !!playbackController;
    const previous = progress[selected.id];
    selected.episode = number; progress[selected.id] = {series:selected.series, episode:number, seconds:previous?.series === selected.series && previous?.episode === number ? Number(previous.seconds) || 0 : 0};
    try { localStorage.setItem(PROGRESS, JSON.stringify(progress)); } catch {}
    const favorite = library.find(x => x.id === selected.id); if (favorite) { favorite.series = selected.series; favorite.episode = number; save(); }
    stop();
    $('videos-selected').textContent = `${number}화`; $('videos-picker-open').textContent = `${number}화 ▾`; updateResume();
    $('videos-jump').value = String(number); $('videos-jump-status').hidden = true;
    $('videos-original').href = watchUrl(selected);
    $('videos-episodes').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.episode) === number)));
    const eps = catalog.series.find(s => s.id === selected.series).episodes, i = eps.indexOf(number);
    $('videos-prev').disabled = i <= 0; $('videos-next').disabled = i < 0 || i >= eps.length-1;
    revealEpisode();
    if (playing || autoplay) play();
  }
  function renderSeries() {
    const entries = catalog.series.find(s => s.id === selected.series) || catalog.series[0];
    selected.series = entries.id; $('videos-series').value = String(entries.id);
    $('videos-episode-count').textContent = `총 ${entries.episodes.length.toLocaleString()}화`;
    $('videos-episodes').replaceChildren(...entries.episodes.map(ep => {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.episode = String(ep); b.textContent = `${ep}화`; b.onclick = () => pickEpisode(ep); return b;
    }));
    chooseEpisode(entries.episodes.includes(selected.episode) ? selected.episode : entries.episodes[0]);
  }
  async function selectWork(item, push = true) {
    if (!$('videos-browse').hidden) listScroll = window.scrollY;
    const savedProgress = progress[item.id];
    const resume = savedProgress && parseWatchUrl(watchUrl({...item, ...savedProgress}));
    closePicker(false);
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
  async function play() {
    if (!selected || !catalog) return;
    stop();
    const version = playerVersion, item = {...selected};
    const current = () => version === playerVersion;
    let fallbackUsed = false;
    function fallback() {
      if (!current() || fallbackUsed) return;
      fallbackUsed = true; clearTimeout(playbackTimer); hlsPlayer?.destroy(); hlsPlayer = null;
      const video = $('videos-player').querySelector('video');
      if (video) { video.pause(); video.removeAttribute('src'); video.load(); }
      const frame = document.createElement('iframe');
      frame.src = watchUrl(item) + '#linktv-video'; frame.title = `${item.title} ${item.episode}화 재생`;
      frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
      frame.setAttribute('allow', 'fullscreen; autoplay; encrypted-media; picture-in-picture');
      frame.setAttribute('scrolling', 'no'); frame.className = 'videos-source-crop'; frame.allowFullscreen = true;
      frame.referrerPolicy = 'no-referrer'; $('videos-player').replaceChildren(frame);
      const resize = () => { frame.style.transform = `scale(${($('videos-player').clientWidth || 560) / 560})`; };
      resize(); if (window.ResizeObserver) { cropObserver = new window.ResizeObserver(resize); cropObserver.observe($('videos-player')); }
      playLabel('다시 불러오기');
    }
    const message = document.createElement('p'); message.textContent = '영상 연결 중…'; $('videos-player').replaceChildren(message);
    playLabel('연결 중…', true);
    const controller = new AbortController(); playbackController = controller;
    const timeout = setTimeout(() => { controller.abort(); fallback(); }, 16000);
    try {
      const response = await fetch(`/api/videos/playback?id=${item.id}&series=${item.series}&episode=${item.episode}`, {signal:controller.signal,cache:'no-store'});
      if (!response.ok) throw Error('no direct player');
      const data = await response.json(); if (!current() || fallbackUsed) return;
      const video = document.createElement('video'); video.controls = true; video.playsInline = true; video.preload = 'auto'; video.crossOrigin = 'anonymous';
      video.setAttribute('aria-label', `${item.title} ${item.episode}화`);
      for (const entry of data.tracks || []) {
        const track = document.createElement('track'); track.kind = 'subtitles'; track.src = entry.src; track.srclang = entry.language; track.label = entry.label; track.default = true; video.append(track);
      }
      let lastSaved = 0;
      video.onloadedmetadata = () => {
        const seconds = Number(progress[item.id]?.seconds) || 0;
        if (current() && seconds > 0 && seconds < video.duration - 5) video.currentTime = seconds;
      };
      video.ontimeupdate = () => {
        if (!current() || !Number.isFinite(video.currentTime)) return;
        const seconds = Math.floor(video.currentTime);
        if (Math.abs(seconds - lastSaved) < 5) return;
        lastSaved = seconds; progress[item.id] = {series:item.series, episode:item.episode, seconds};
        try { localStorage.setItem(PROGRESS, JSON.stringify(progress)); } catch {}
        updateResume();
      };
      video.onerror = fallback;
      video.onloadeddata = () => { if (current()) clearTimeout(playbackTimer); };
      $('videos-player').replaceChildren(video);
      playbackTimer = setTimeout(fallback, 12000);
      if (video.canPlayType('application/vnd.apple.mpegurl')) video.src = data.src;
      else if (window.Hls?.isSupported()) {
        hlsPlayer = new window.Hls(); hlsPlayer.on(window.Hls.Events.ERROR, (event, info) => { if (info.fatal) fallback(); });
        hlsPlayer.loadSource(data.src); hlsPlayer.attachMedia(video);
      } else { fallback(); return; }
      playLabel('다시 불러오기');
      const autoplay = video.play(); if (autoplay?.catch) autoplay.catch(() => {});
    } catch { fallback(); }
    finally { clearTimeout(timeout); if (current()) playbackController = null; }
  }
  $('videos-jump-form').onsubmit = event => {
    event.preventDefault(); if (!catalog) return;
    const number = Number($('videos-jump').value), eps = catalog.series.find(s => s.id === selected.series).episodes;
    if (!eps.includes(number)) { $('videos-jump-status').textContent = '이 시리즈에 없는 회차예요. 아래 목록에서 선택해 주세요.'; $('videos-jump-status').hidden = false; return; }
    pickEpisode(number);
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
    if (ep) chooseEpisode(ep, true);
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
