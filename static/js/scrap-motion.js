/* Genie save uses a visual copy; originals and feed scroll never move. */
(() => {
  'use strict';
  const active = new Map();
  const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function smooth(value) {
    const t = Math.max(0, Math.min(1, value));
    return t * t * (3 - 2 * t);
  }
  function stripGeometry(rect, destination, t, v, step) {
    const top = rect.top + (destination.y - rect.top) * smooth((t - .30) / .70);
    const bottom = rect.bottom + (destination.y - rect.bottom) * smooth(t / .52);
    const shrink = smooth((t - (1 - v) * .4) / .6);
    const width = rect.width * (1 - shrink) + 5 * shrink;
    const center = rect.left + rect.width / 2 + (destination.x - rect.left - rect.width / 2) * shrink;
    return {x: center - width / 2, y: top + (bottom - top) * v,
      sx: width / rect.width, sy: Math.max(.001, (bottom - top) / rect.height)};
  }
  function cancel(key) {
    const effect = active.get(key);
    if (!effect) return;
    cancelAnimationFrame(effect.raf);
    clearTimeout(effect.timer);
    effect.layer.remove();
    active.delete(key);
    if (!Array.from(active.values()).some(other => other.footer === effect.footer)) {
      effect.footer?.classList.remove('scrap-motion-anchor');
    }
  }
  function unsave(button) {
    if (!button) return;
    cancel(button.dataset.key);
    if (reduced()) return;
    // CSS SVG motion is more reliable on iOS than SVG Web Animations.
    button.classList.remove('scrap-unsaving');
    void button.offsetWidth;
    button.classList.add('scrap-unsaving');
    setTimeout(() => button.classList.remove('scrap-unsaving'),280);
  }
  function save(button) {
    if (!button || reduced()) return;
    const key = button.dataset.key;
    cancel(key);
    const target = document.getElementById('scrap-open-btn');
    const source = button.closest('.card') || button;
    if (!target || !source.isConnected) return;
    const rect = source.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const layer = document.createElement('div');
    layer.className = 'scrap-genie';
    layer.setAttribute('aria-hidden','true');
    layer.inert = true;
    const copy = source.cloneNode(true);
    const originals = [source, ...source.querySelectorAll('*')];
    const copies = [copy, ...copy.querySelectorAll('*')];
    // Snapshot computed styles once, then reuse the styled copy in all bands.
    originals.forEach((node, index) => {
      const style = getComputedStyle(node);
      for (const property of style) copies[index].style.setProperty(property, style.getPropertyValue(property));
      copies[index].removeAttribute('id');
      copies[index].removeAttribute('autofocus');
      copies[index].removeAttribute('name');
    });
    copy.querySelectorAll('iframe,video,audio,script').forEach(node => node.remove());
    Object.assign(copy.style,{position:'absolute',left:'0',width:rect.width+'px',height:rect.height+'px',
      minHeight:'0',maxWidth:'none',margin:'0',transform:'none',boxSizing:'border-box'});
    const bands = 32, step = 1 / bands, bandHeight = rect.height / bands, slices = [];
    for (let i = 0; i < bands; i++) {
      const slice = document.createElement('div');
      slice.className = 'scrap-genie-slice';
      slice.style.width = rect.width + 'px';
      slice.style.height = (bandHeight + .8) + 'px';
      const fragment = copy.cloneNode(true);
      fragment.style.top = (-i * bandHeight) + 'px';
      slice.appendChild(fragment);
      layer.appendChild(slice);
      slices.push(slice);
    }
    // Scrolling hides the footer. Reveal it before measuring the destination,
    // otherwise saves below the first article are skipped as offscreen.
    const footer = target.closest('.bottombar');
    footer?.classList.add('scrap-motion-anchor');
    const anchor = target.getBoundingClientRect();
    if (anchor.width <= 0 || anchor.height <= 0 || anchor.bottom <= 0 || anchor.top >= window.innerHeight) {
      if (!Array.from(active.values()).some(other => other.footer === footer)) footer?.classList.remove('scrap-motion-anchor');
      return;
    }
    const destination = {x:anchor.left + anchor.width / 2,y:anchor.top + Math.min(26,anchor.height / 2)};
    document.body.appendChild(layer);
    const effect = {layer,footer,raf:0,timer:0};
    active.set(key,effect);
    let start;
    const render = now => {
      if (active.get(key) !== effect) return;
      if (reduced() || !source.isConnected || !target.isConnected) { cancel(key); return; }
      if (start === undefined) start = now;
      const t = Math.min(1,(now-start)/520);
      slices.forEach((slice,i) => {
        const g = stripGeometry(rect,destination,t,i*step,step);
        slice.style.transform = `translate3d(${g.x}px,${g.y}px,0) scale(${g.sx},${g.sy})`;
      });
      if (t < 1) effect.raf = requestAnimationFrame(render);
      else {
        cancel(key);
        target.classList.remove('scrap-pop');
        void target.offsetWidth;
        target.classList.add('scrap-pop');
        setTimeout(() => target.classList.remove('scrap-pop'),500);
      }
    };
    // Clean up even if the browser pauses animation frames in the background.
    effect.timer = setTimeout(() => cancel(key),1200);
    effect.raf = requestAnimationFrame(render);
  }
  function cancelAll() { Array.from(active.keys()).forEach(cancel); }
  document.addEventListener('visibilitychange',() => { if (document.hidden) cancelAll(); });
  window.addEventListener('pagehide',cancelAll);
  window.addEventListener('resize',cancelAll);
  window.HScopeScrapMotion = {save,unsave,cancel};
})();
