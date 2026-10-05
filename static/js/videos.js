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
  function episodeRanges(episodes) {
    const groups = new Map();
    for (const episode of episodes) {
      const start = Math.floor((episode - 1) / 100) * 100 + 1;
      if (!groups.has(start)) groups.set(start, []);
      groups.get(start).push(episode);
    }
    return Array.from(groups, ([start, values]) => ({start, end:values[values.length - 1], episodes:values}));
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
  let airplayCleanup = null;
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
    cancelAvailability();
    ++requestVersion; selected = null; catalog = null; stop(); $('videos-detail').hidden = true; $('videos-browse').hidden = false; status('', true);
    renderLibrary();
    if (restore && !$('view-videos').hidden) window.scrollTo({top:listScroll,left:0,behavior:'instant'});
  }
  function detailUrl(id) { const url = new URL(location.href); if (id) url.searchParams.set('video',id); else url.searchParams.delete('video'); return url; }
  function makeCard(item, resume = false) {
    const card = document.createElement('article'); card.className = 'videos-work';
    const b = document.createElement('button'); b.type = 'button'; b.className = 'videos-work-open';
    const image = cache.get(item.id)?.image || item.image || allWorks.find(x => x.id === item.id)?.image;
    const poster = document.createElement('div'); poster.className = 'videos-poster'; poster.setAttribute('aria-hidden','true');
    const placeholder = document.createElement('span'); placeholder.className = 'videos-poster-placeholder'; placeholder.textContent = 'HSCOPE'; poster.append(placeholder);
    if (image) { const img = document.createElement('img'); img.src = image; img.alt = ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.onerror = () => img.remove(); poster.append(img); }
    if (resume) { const badge = document.createElement('span'); badge.className = 'videos-card-badge'; badge.textContent = '이어보기'; poster.append(badge); }
    b.append(poster);
    const name = document.createElement('strong'); name.textContent = item.title; name.title = item.title; b.append(name);
    const info = document.createElement('small'), saved = progress[item.id];
    info.textContent = resume && saved ? `${saved.episode}화 · ${Math.floor((saved.seconds || 0) / 60)}분 시청` : item.description ? `회차 ${item.description}` : '작품 정보 보기'; b.append(info);
    b.onclick = async () => { await selectWork(item); if (resume && catalog && selected?.id === item.id) play(); };
    const favorite = document.createElement('button'); favorite.type = 'button'; favorite.className = 'videos-save';
    const savedItem = library.some(x => x.id === item.id); favorite.textContent = savedItem ? '✓ 내 목록' : '+ 내 목록';
    favorite.setAttribute('aria-pressed', String(savedItem)); favorite.setAttribute('aria-label', `${item.title} ${favoriteLabel(item)}`);
    favorite.onclick = () => toggleFavorite(item); card.append(b, favorite); return card;
  }
  function renderShelves(query) {
    const show = scope === 'all' && !query;
    $('videos-shelves').hidden = !show; $('videos-hero').hidden = !show || !allWorks.length;
    if (!show) return;
    const candidates = discoveryRows(library, allWorks, 'all', '');
    const continuing = candidates.filter(item => Number(progress[item.id]?.seconds) > 0).sort((a,b) => (progress[b.id].updatedAt || 0) - (progress[a.id].updatedAt || 0));
    for (const [section, target, rows, resume] of [['videos-continue-section','videos-continue',continuing,true],['videos-my-section','videos-my-rail',library,false],['videos-picks-section','videos-picks',DEFAULT_LIBRARY.map(item => allWorks.find(x => x.id === item.id)).filter(Boolean),false]]) {
      $(section).hidden = !rows.length; $(target).replaceChildren(...rows.slice(0,16).map(item => makeCard(item,resume)));
    }
    const featured = continuing[0] || allWorks.find(x => x.id === '19240') || allWorks[0];
    if (!featured) return;
    const hero = $('videos-hero'); hero.replaceChildren();
    if (featured.image) { const image = document.createElement('img'); image.src = featured.image; image.alt = ''; image.referrerPolicy = 'no-referrer'; image.onerror = () => image.remove(); hero.append(image); }
    const content = document.createElement('div'); content.className = 'videos-hero-content';
    const eyebrow = document.createElement('span'); eyebrow.className = 'videos-eyebrow'; eyebrow.textContent = continuing.length ? '멈췄던 이야기, 이어서' : '오늘 만날 이야기';
    const title = document.createElement('h3'); title.textContent = featured.title;
    const description = document.createElement('p'); description.textContent = continuing.length ? `${progress[featured.id].episode}화부터 다시 시작하세요.` : '작품을 열고 원하는 회차를 골라 감상하세요.';
    const actions = document.createElement('div'); actions.className = 'videos-hero-actions';
    const open = document.createElement('button'); open.type = 'button'; open.textContent = continuing.length ? '▶ 이어보기' : '▶ 작품 보기';
    open.onclick = async () => { await selectWork(featured); if (continuing.length && catalog && selected?.id === featured.id) play(); };
    const saveButton = document.createElement('button'); saveButton.type = 'button'; saveButton.textContent = favoriteLabel(featured); saveButton.onclick = () => toggleFavorite(featured);
    actions.append(open,saveButton); content.append(eyebrow,title,description,actions); hero.append(content);
  }
  function renderLibrary(append = false) {
    const query = $('videos-search').value.trim(), rows = discoveryRows(library, allWorks, scope, query);
    $('videos-count').textContent = `총 ${rows.length.toLocaleString()}개${query ? ' · 검색 결과' : ''}${indexLoading ? ' · 전체 목록 불러오는 중…' : ''}`;
    $('videos-grid-heading').textContent = query ? '검색 결과' : scope === 'saved' ? '내 목록의 모든 작품' : '모든 작품';
    const cards = rows.slice(append ? Math.max(0,visibleCount-40) : 0,visibleCount).map(item => makeCard(item));
    if (append) $('videos-library').append(...cards); else { $('videos-library').replaceChildren(...cards); renderShelves(query); }
    const more = rows.length > visibleCount;
    $('videos-sentinel').hidden = !more; $('videos-sentinel').textContent = more ? '스크롤하면 다음 작품을 불러와요' : '';
    if (!rows.length) { const p = document.createElement('p'); p.className = 'videos-empty'; p.textContent = indexLoading && scope === 'all' ? '전체 작품 목록을 불러오고 있어요…' : scope === 'saved' && !query ? '마음에 드는 작품을 내 목록에 추가해 보세요.' : '검색 결과가 없어요. 다른 제목으로 찾아보세요.'; $('videos-library').append(p); }
  }
  let loadingMore = false;
  function loadMore() {
    if (loadingMore || $('view-videos').hidden || $('videos-browse').hidden || $('videos-sentinel').hidden) return;
    loadingMore = true; visibleCount += 40; renderLibrary(true);
    window.requestAnimationFrame(() => { loadingMore = false; if (!$('videos-sentinel').hidden && $('videos-sentinel').getBoundingClientRect().top < window.innerHeight + 450) loadMore(); });
  }
  if (window.IntersectionObserver) { const observer = new window.IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) loadMore(); }, {rootMargin:'450px'}); observer.observe($('videos-sentinel')); }
  else window.addEventListener('scroll', () => { if ($('videos-sentinel').getBoundingClientRect().top < window.innerHeight + 450) loadMore(); }, {passive:true});
  function playLabel(label, disabled = false) { $('videos-resume-title').textContent = label; $('videos-play').disabled = disabled; }
  function updateResume() {
    if (!selected) return;
    const seconds = Math.max(0, Math.floor(Number(progress[selected.id]?.seconds) || 0));
    $('videos-resume-info').textContent = `${selected.episode}화${seconds ? ' · ' + Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0') : ''}`;
  }
  let rangeStart = 1;
  let availabilityRun = 0, availabilityController = null, availabilityContext = '';
  function cancelAvailability() { ++availabilityRun; availabilityController?.abort(); availabilityController = null; availabilityContext = ''; }
  function episodeState(ep) {
    const entry = catalog?.availability?.[`${selected.series}:${ep}`];
    if (entry?.status === 'unknown' && Date.now()/1000 - entry.checked_at > 60) return undefined;
    return typeof entry === 'string' ? entry : entry?.status;
  }
  function paintEpisodeStates() {
    for (const button of $('videos-episodes').querySelectorAll('button')) {
      const ep = Number(button.dataset.episode), state = episodeState(ep);
      button.dataset.availability = state || 'checking';
      button.textContent = `${ep}화${state === 'missing' ? ' · 영상 없음' : state === 'unknown' ? ' · 확인 불가' : !state ? ' · 확인 중' : ' · 연결 있음'}`;
      button.setAttribute('aria-label', `${ep}화${state === 'missing' ? ', 원출처 영상 없음. 선택하면 다시 확인' : !state || state === 'unknown' ? ', 영상 연결 확인 중 또는 확인 불가' : ''}`);
    }
  }
  async function checkEpisodePage() {
    if (!catalog || !selected || $('view-videos').hidden) return;
    const context = `${selected.id}:${selected.series}:${rangeStart}`;
    if (context === availabilityContext && availabilityController && !availabilityController.signal.aborted) return;
    availabilityContext = context;
    const run = ++availabilityRun, work = selected.id, series = selected.series, data = catalog;
    availabilityController?.abort(); const controller = new AbortController(); availabilityController = controller;
    const numbers = Array.from($('videos-episodes').querySelectorAll('button')).map(b => Number(b.dataset.episode)).filter(ep => !episodeState(ep)).sort((a,b) => Math.abs(a-selected.episode)-Math.abs(b-selected.episode));
    for (let offset = 0; offset < numbers.length; offset += 2) {
      if (run !== availabilityRun || selected?.id !== work || selected.series !== series) break;
      try {
        const response = await fetch(`/api/videos/availability?id=${work}&series=${series}&episodes=${numbers.slice(offset,offset+2).join(',')}`, {signal:controller.signal});
        if (!response.ok) throw Error('availability unavailable');
        const result = await response.json();
        const states = Object.fromEntries(Object.entries(result.states || {}).map(([key,value]) => [key,value === 'unknown' ? {status:value,checked_at:Date.now()/1000} : value]));
        data.availability = {...data.availability, ...states};
        if (run === availabilityRun && catalog === data) paintEpisodeStates();
      } catch {
        if (run === availabilityRun && catalog === data && !controller.signal.aborted) {
          for (const ep of numbers.slice(offset)) data.availability = {...data.availability,[`${series}:${ep}`]:{status:'unknown',checked_at:Date.now()/1000}};
          paintEpisodeStates();
        }
        break;
      }
    }
    if (run === availabilityRun) availabilityController = null;
  }
  let sheetOverflow = '';
  function closePicker(focus = true) {
    const sheet = $('videos-picker'); if (!sheet.open) return;
    sheet.close(); document.documentElement.style.overflow = sheetOverflow;
    $('videos-picker-open').setAttribute('aria-expanded', 'false');
    if (focus) $('videos-picker-open').focus({preventScroll:true});
  }
  function sizePicker() {
    const height = window.visualViewport?.height || window.innerHeight;
    $('videos-picker').style.setProperty('--sheet-height', `${Math.min(720, Math.floor(height * .88))}px`);
  }
  function openPicker() {
    if (!catalog || $('videos-picker').open) return;
    sizePicker(); sheetOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    browseEpisode(selected.episode);
    $('videos-picker').showModal(); $('videos-picker-open').setAttribute('aria-expanded', 'true');
    revealEpisode();
    checkEpisodePage();
  }
  function pickEpisode(number) { closePicker(); chooseEpisode(number, true); }
  $('videos-picker-open').onclick = openPicker;
  $('videos-picker-close').onclick = () => closePicker();
  $('videos-picker').addEventListener('cancel', event => { event.preventDefault(); closePicker(); });
  $('videos-picker').onclick = event => { if (event.target === $('videos-picker')) { const r = $('videos-picker').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closePicker(); } };
  window.addEventListener('resize', () => { if ($('videos-picker').open) { sizePicker(); revealEpisode(); } });
  window.visualViewport?.addEventListener('resize', () => { if ($('videos-picker').open) sizePicker(); });
  function stop() { airplayCleanup?.(); airplayCleanup = null; $('videos-airplay-controls').hidden = true; $('videos-airplay-return').hidden = true; $('videos-airplay-status').textContent = ''; ++playerVersion; cropObserver?.disconnect(); cropObserver = null; playbackController?.abort(); playbackController = null; clearTimeout(playbackTimer); hlsPlayer?.destroy(); hlsPlayer = null; const video = $('videos-player').querySelector('video'); if (video) { video.pause(); video.removeAttribute('src'); video.load(); } $('videos-player').replaceChildren(); const p = document.createElement('p'); p.textContent = '재생을 눌러 선택한 회차를 감상하세요.'; $('videos-player').append(p); playLabel(selected && Number(progress[selected.id]?.seconds) > 0 ? '이어보기' : '재생하기'); }
  function revealEpisode(number = selected.episode) {
    const list = $('videos-episodes'), button = Array.from(list.querySelectorAll('button')).find(b => Number(b.dataset.episode) === number);
    if (button) list.scrollTop = Math.max(0, button.offsetTop - (list.clientHeight - button.offsetHeight) / 2);
  }
  function chooseEpisode(number, autoplay = false) {
    const playing = !!$('videos-player').querySelector('iframe, video') || !!playbackController;
    const previous = progress[selected.id];
    selected.episode = number; progress[selected.id] = {series:selected.series, episode:number, seconds:previous?.series === selected.series && previous?.episode === number ? Number(previous.seconds) || 0 : 0, updatedAt:previous?.updatedAt || 0};
    try { localStorage.setItem(PROGRESS, JSON.stringify(progress)); } catch {}
    const favorite = library.find(x => x.id === selected.id); if (favorite) { favorite.series = selected.series; favorite.episode = number; save(); }
    stop();
    browseEpisode(number);
    $('videos-current-page').textContent = `현재 ${number}화`;
    const latest = currentEpisodes().slice(-1)[0]; $('videos-latest-page').textContent = `최신 ${latest}화`;
    $('videos-selected').textContent = `${number}화`; $('videos-picker-open').textContent = `${number}화 ▾`; updateResume();
    $('videos-jump').value = String(number); $('videos-jump-status').hidden = true;
    $('videos-original').href = `/api/videos/original?id=${selected.id}&series=${selected.series}&episode=${selected.episode}`;
    $('videos-episodes').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.episode) === number)));
    const eps = catalog.series.find(s => s.id === selected.series).episodes, i = eps.indexOf(number);
    $('videos-prev').disabled = i <= 0; $('videos-next').disabled = i < 0 || i >= eps.length-1;
    revealEpisode();
    if (playing || autoplay) play();
  }
  function currentEpisodes() { return catalog.series.find(s => s.id === selected.series).episodes; }
  function renderEpisodePage() {
    const ranges = episodeRanges(currentEpisodes());
    const page = ranges.find(r => r.start === rangeStart) || ranges[0]; rangeStart = page.start;
    $('videos-range').value = String(rangeStart);
    $('videos-range-row').hidden = ranges.length <= 1;
    const index = ranges.indexOf(page);
    $('videos-range-prev').disabled = index <= 0; $('videos-range-next').disabled = index >= ranges.length - 1;
    $('videos-range-info').textContent = `${page.episodes[0]}~${page.end}화 · ${index + 1}/${ranges.length}구간`;
    $('videos-episodes').replaceChildren(...page.episodes.map(ep => {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.episode = String(ep); b.textContent = `${ep}화`;
      b.setAttribute('aria-pressed', String(ep === selected.episode)); b.onclick = () => pickEpisode(ep); return b;
    }));
    $('videos-episodes').scrollTop = 0;
    paintEpisodeStates();
    checkEpisodePage();
  }
  function browseEpisode(number) {
    rangeStart = Math.floor((number - 1) / 100) * 100 + 1;
    renderEpisodePage(); if ($('videos-picker').open) revealEpisode(number);
  }
  function renderSeries() {
    const entries = catalog.series.find(s => s.id === selected.series) || catalog.series[0];
    selected.series = entries.id; $('videos-series').value = String(entries.id);
    $('videos-series-label').hidden = catalog.series.length <= 1;
    $('videos-episode-count').textContent = `총 ${entries.episodes.length.toLocaleString()}화`;
    const ranges = episodeRanges(entries.episodes);
    $('videos-range').replaceChildren(...ranges.map(r => { const o = document.createElement('option'); o.value = String(r.start); o.textContent = `${r.start}~${r.end}화`; return o; }));
    const number = entries.episodes.includes(selected.episode) ? selected.episode : entries.episodes[0];
    rangeStart = Math.floor((number - 1) / 100) * 100 + 1; renderEpisodePage(); chooseEpisode(number);
  }
  $('videos-range').onchange = () => { rangeStart = Number($('videos-range').value); renderEpisodePage(); };
  for (const [id, offset] of [['videos-range-prev',-1],['videos-range-next',1]]) $(id).onclick = () => {
    const ranges = episodeRanges(currentEpisodes()), target = ranges[ranges.findIndex(r => r.start === rangeStart) + offset];
    if (target) { rangeStart = target.start; renderEpisodePage(); }
  };
  $('videos-current-page').onclick = () => browseEpisode(selected.episode);
  $('videos-latest-page').onclick = () => { const episodes = currentEpisodes(); browseEpisode(episodes[episodes.length - 1]); };
  async function selectWork(item, push = true) {
    if (!$('videos-browse').hidden) listScroll = window.scrollY;
    const savedProgress = progress[item.id];
    const resume = savedProgress && parseWatchUrl(watchUrl({...item, ...savedProgress}));
    closePicker(false);
    cancelAvailability();
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
  function setupAirPlay(video, current, hasSubtitles) {
    const controls = $('videos-airplay-controls'), button = $('videos-airplay'), back = $('videos-airplay-return'), label = $('videos-airplay-status');
    const supported = typeof video.webkitShowPlaybackTargetPicker === 'function' || !!video.remote?.prompt;
    controls.hidden = !supported;
    if (!supported) return;
    let repairPending = false;
    const wireless = () => !!video.webkitCurrentPlaybackTargetIsWireless || video.remote?.state === 'connected';
    const repairNativeControls = () => {
      if (!current() || wireless() || repairPending || video.webkitDisplayingFullscreen || document.fullscreenElement === video) return;
      repairPending = true;
      video.setAttribute('x-webkit-airplay', 'allow'); video.disableRemotePlayback = false;
      // Rebuild the native controls without changing src, playback position or text tracks.
      video.controls = false;
      const frame = window.requestAnimationFrame || (callback => setTimeout(callback, 20));
      frame(() => frame(() => {
        if (current()) video.controls = true;
        repairPending = false;
      }));
    };
    const refresh = () => {
      if (!current()) return;
      const wireless = !!video.webkitCurrentPlaybackTargetIsWireless || video.remote?.state === 'connected';
      back.hidden = !wireless; button.textContent = wireless ? 'AirPlay 기기 변경' : 'AirPlay';
      button.disabled = false;
      label.textContent = wireless ? 'AirPlay 연결 중' : '';
      if (wireless && hasSubtitles) label.textContent += ' · TV 재생 메뉴에서 한국어 자막을 선택해 주세요.';
    };
    const picker = () => {
      if (!current()) return;
      try {
        if (typeof video.webkitShowPlaybackTargetPicker === 'function') video.webkitShowPlaybackTargetPicker();
        else video.remote.prompt().catch(() => refresh());
      } catch { label.textContent = '기기 선택창을 다시 열어 주세요.'; }
      refresh();
    };
    button.onclick = picker;
    back.onclick = () => { picker(); label.textContent = '기기 선택창에서 iPhone 또는 이 기기를 선택하면 연결이 해제돼요.'; };
    // Device availability can temporarily report unavailable after cancelling the picker.
    // Keep the control mounted while this video exists so it can always reopen.
    video.addEventListener('webkitplaybacktargetavailabilitychanged', () => { refresh(); repairNativeControls(); });
    video.addEventListener('webkitcurrentplaybacktargetiswirelesschanged', () => { refresh(); repairNativeControls(); });
    video.addEventListener('webkitendfullscreen', repairNativeControls);
    const wake = () => { if (document.visibilityState !== 'hidden') { refresh(); repairNativeControls(); } };
    window.addEventListener('focus', wake); window.addEventListener('pageshow', wake);
    document.addEventListener?.('visibilitychange', wake);
    airplayCleanup = () => {
      window.removeEventListener?.('focus', wake); window.removeEventListener?.('pageshow', wake);
      document.removeEventListener?.('visibilitychange', wake);
    };
    $('videos-player-repair').onclick = () => {
      if (!current() || wireless()) { label.textContent = '이 기기로 전환한 뒤 재생기를 복구해 주세요.'; return; }
      if (selected && Number.isFinite(video.currentTime)) {
        progress[selected.id] = {series:selected.series, episode:selected.episode, seconds:video.currentTime};
        try { localStorage.setItem(PROGRESS, JSON.stringify(progress)); } catch {}
      }
      play({restorePaused:video.paused});
    };
    for (const event of ['loadedmetadata', 'playing', 'pause']) video.addEventListener(event, refresh);
    if (video.remote?.addEventListener) for (const event of ['connect','disconnect','connecting']) video.remote.addEventListener(event, refresh);
    refresh();
  }
  async function play(options = {}) {
    if (!selected || !catalog) return;
    stop(); status('', true);
    const version = playerVersion, item = {...selected};
    const current = () => version === playerVersion;
    let fallbackUsed = false;
    function fallback() {
      if (!current() || fallbackUsed) return;
      fallbackUsed = true; $('videos-airplay-controls').hidden = true; clearTimeout(playbackTimer); hlsPlayer?.destroy(); hlsPlayer = null;
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
      const data = await response.json();
      if (!response.ok && data.code === 'video_missing') {
        if (!current()) return; fallbackUsed = true;
        catalog.availability = {...catalog.availability, [`${item.series}:${item.episode}`]: 'missing'}; paintEpisodeStates();
        const missing = document.createElement('p'); missing.textContent = data.error;
        $('videos-player').replaceChildren(missing); status(data.error, true); playLabel('다시 확인하기'); return;
      }
      if (!response.ok) throw Error('no direct player'); if (!current() || fallbackUsed) return;
      const video = document.createElement('video'); video.controls = true; video.playsInline = true; video.preload = 'auto'; video.crossOrigin = 'anonymous';
      video.setAttribute('x-webkit-airplay', 'allow'); video.disableRemotePlayback = false;
      video.setAttribute('aria-label', `${item.title} ${item.episode}화`);
      for (const entry of data.native_src ? [] : data.tracks || []) {
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
        lastSaved = seconds; progress[item.id] = {series:item.series, episode:item.episode, seconds, updatedAt:Date.now()};
        try { localStorage.setItem(PROGRESS, JSON.stringify(progress)); } catch {}
        updateResume();
      };
      const mediaFailure = () => {
        if (!current() || fallbackUsed) return;
        fallbackUsed = true; clearTimeout(playbackTimer); $('videos-airplay-controls').hidden = true;
        video.pause(); hlsPlayer?.destroy(); hlsPlayer = null;
        const failure = document.createElement('p'); failure.textContent = '원출처 영상에 연결하지 못했어요. 삭제되었거나 제공이 중단된 영상일 수 있어요.';
        $('videos-player').replaceChildren(failure); status(failure.textContent, true); playLabel('다시 확인하기');
      };
      video.onerror = mediaFailure;
      video.onloadeddata = () => { if (current()) { clearTimeout(playbackTimer); catalog.availability = {...catalog.availability, [`${item.series}:${item.episode}`]: 'available'}; paintEpisodeStates(); } };
      $('videos-player').replaceChildren(video);
      setupAirPlay(video, current, !!data.tracks?.length);
      playbackTimer = setTimeout(() => { if (!video.webkitCurrentPlaybackTargetIsWireless) mediaFailure(); }, 12000);
      if (video.canPlayType('application/vnd.apple.mpegurl')) video.src = data.native_src || data.src;
      else if (window.Hls?.isSupported()) {
        hlsPlayer = new window.Hls(); hlsPlayer.on(window.Hls.Events.ERROR, (event, info) => { if (info.fatal) mediaFailure(); });
        hlsPlayer.loadSource(data.native_src || data.src); hlsPlayer.attachMedia(video);
      } else { fallback(); return; }
      playLabel('다시 불러오기');
      if (!options.restorePaused) { const autoplay = video.play(); if (autoplay?.catch) autoplay.catch(() => {}); }
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
