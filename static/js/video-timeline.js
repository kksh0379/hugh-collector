(function (root) {
  function attach(video, ui, current) {
    let dragging = false, target = null, timer = null;
    const bindings = [];
    const listen = (el, event, fn) => { el.addEventListener(event, fn); bindings.push([el,event,fn]); };
    const clock = value => {
      const seconds = Math.max(0, Math.floor(Number(value) || 0));
      return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2,'0')}`;
    };
    const duration = () => Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0;
    const render = () => {
      if (!current()) return;
      const length = duration(), seconds = dragging ? Number(ui.seek.value) : (target ?? video.currentTime);
      ui.seek.disabled = !length;
      ui.seek.max = String(length || 1);
      if (!dragging) ui.seek.value = String(Math.max(0, seconds || 0));
      ui.time.textContent = `${clock(seconds)} / ${clock(length)}`;
      ui.toggle.textContent = video.paused ? '재생' : '일시정지';
      ui.toggle.setAttribute('aria-label', video.paused ? '영상 재생' : '영상 일시정지');
      ui.back.disabled = ui.forward.disabled = !length;
    };
    const confirmed = () => {
      if (target !== null && !video.seeking && Math.abs(video.currentTime - target) < 2) {
        target = null; clearTimeout(timer); ui.status.textContent = '';
      }
      render();
    };
    const seek = seconds => {
      if (!current() || !duration()) return;
      dragging = false;
      target = Math.max(0, Math.min(duration() - .1, Number(seconds) || 0));
      clearTimeout(timer); ui.status.textContent = '재생 위치 이동 중…';
      try { video.currentTime = target; }
      catch { target = null; ui.status.textContent = '위치를 이동하지 못했어요. 다시 시도해 주세요.'; render(); return; }
      // One command per gesture; do not continually send seeks to an AirPlay receiver.
      render();
      timer = setTimeout(() => {
        if (!current() || target === null) return;
        target = null; ui.status.textContent = '기기 응답이 늦어요. 재생 위치를 다시 선택해 주세요.'; render();
      }, 15000);
    };
    listen(ui.seek,'input', () => { dragging = true; ui.time.textContent = `${clock(ui.seek.value)} / ${clock(duration())}`; });
    listen(ui.seek,'change', () => seek(ui.seek.value));
    listen(ui.seek,'blur', () => { if (dragging) { dragging = false; render(); } });
    listen(ui.seek,'pointercancel', () => { dragging = false; render(); });
    listen(ui.back,'click', () => seek((target ?? video.currentTime) - 10));
    listen(ui.forward,'click', () => seek((target ?? video.currentTime) + 10));
    listen(ui.toggle,'click', () => {
      if (!current()) return;
      if (video.paused) { const result = video.play(); result?.catch?.(() => { ui.status.textContent = '재생 버튼을 다시 눌러 주세요.'; }); }
      else video.pause();
    });
    for (const event of ['loadedmetadata','durationchange','timeupdate','seeked','play','pause','webkitcurrentplaybacktargetiswirelesschanged']) listen(video,event,confirmed);
    ui.bar.hidden = false; ui.status.textContent = ''; render();
    return { pending: () => target !== null, destroy: () => {
      clearTimeout(timer); bindings.forEach(([el,event,fn]) => el.removeEventListener(event,fn));
      ui.bar.hidden = true; ui.status.textContent = '';
    }};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {attach};
  else root.HscopeVideoTimeline = {attach};
})(typeof window === 'undefined' ? globalThis : window);
