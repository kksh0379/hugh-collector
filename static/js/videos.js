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
  let library = [{id:'19240', series:1, episode:8, title:'강철의 연금술사'}];
  try {
    const saved = JSON.parse(localStorage.getItem(STORE));
    if (Array.isArray(saved)) {
      const valid = saved.slice(0,100).filter(x => x && parseWatchUrl(watchUrl(x))).map(x => ({...parseWatchUrl(watchUrl(x)), title:String(x.title || `작품 ${x.id}`).slice(0,160)}));
      if (valid.length) library = valid;
    }
  } catch {}
  let selected = null, catalog = null, requestVersion = 0, initialized = false;
  const cache = new Map();
  function save() { try { localStorage.setItem(STORE, JSON.stringify(library)); } catch {} }
  function status(text) { $('videos-status').textContent = text; $('videos-status').hidden = !text; }
  function renderLibrary() {
    $('videos-library').replaceChildren(...library.map(item => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'videos-work';
      b.setAttribute('aria-pressed', String(item.id === selected?.id));
      const image = cache.get(item.id)?.image;
      if (image) { const img = document.createElement('img'); img.src = image; img.alt = ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.onerror = () => img.remove(); b.append(img); }
      const name = document.createElement('strong'); name.textContent = item.title; b.append(name);
      b.onclick = () => selectWork(item); return b;
    }));
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
  window.onShowVideos = () => { if (!initialized) { initialized = true; renderLibrary(); selectWork(library[0]); } };
  window.onHideVideos = () => stop();
})();
