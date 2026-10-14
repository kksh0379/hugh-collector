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
  function receiverLeft(anchor, viewportWidth) {
    const center = anchor.width > 0 ? anchor.left + anchor.width / 2 : viewportWidth - 44;
    return Math.max(16, Math.min(viewportWidth - 72, center - 28));
  }
  function cancel(key) {
    const effect = active.get(key);
    if (!effect) return;
    cancelAnimationFrame(effect.raf);
    clearTimeout(effect.timer);
    effect.layer.remove();
    effect.floating?.remove();
    active.delete(key);
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
  function styledCopy(source, rect) {
    const copy = source.cloneNode(true);
    const originals = [source, ...source.querySelectorAll('*')];
    const copies = [copy, ...copy.querySelectorAll('*')];
    originals.forEach((node,index) => {
      const style = getComputedStyle(node);
      for (const property of style) copies[index].style.setProperty(property,style.getPropertyValue(property));
      copies[index].removeAttribute('id');
      copies[index].removeAttribute('autofocus');
      copies[index].removeAttribute('name');
    });
    copy.querySelectorAll('iframe,video,audio,script,.scrap-crumple-creases').forEach(node => node.remove());
    copy.classList.remove('scrap-removing','scrap-crumpling');
    Object.assign(copy.style,{position:'absolute',left:'0',top:'0',width:rect.width+'px',height:rect.height+'px',
      minHeight:'0',maxWidth:'none',margin:'0',transform:'none',boxSizing:'border-box'});
    return copy;
  }
  async function crumple(card, play) {
    const rect = card.getBoundingClientRect();
    const copy = styledCopy(card,rect);
    const surface = document.createElement('div');
    surface.className = 'scrap-crumple-surface';
    surface.setAttribute('aria-hidden','true'); surface.inert = true;
    const edge = [[0,0],[50,0],[100,0],[100,50],[100,100],[50,100],[0,100],[0,50]];
    const facets = edge.map((p,i) => {
      const q = edge[(i+1)%8];
      const facet = document.createElement('div');
      facet.className = 'scrap-paper-facet';
      facet.style.clipPath = `polygon(50% 50%,${p[0]}% ${p[1]}%,${q[0]}% ${q[1]}%)`;
      facet.appendChild(copy.cloneNode(true));surface.appendChild(facet);return facet;
    });
    card.appendChild(surface);card.classList.add('scrap-crumpling');
    await Promise.all(facets.map((facet,i) => {
      const angle = i*Math.PI/4, dx=Math.cos(angle),dy=Math.sin(angle);
      const shade=i%2?'.68':'1.28';
      return play([
        {opacity:1,transform:'none',filter:'brightness(1)'},
        {opacity:1,transform:`perspective(500px) rotateX(${dy*68}deg) rotateY(${-dx*68}deg) rotate(${i%2?18:-18}deg) scale(.62,.65)`,filter:`brightness(${shade})`,offset:.36},
        {opacity:1,transform:`translate(${dx*4}px,${dy*4}px) rotate(${i*29-80}deg) scale(.14,.25)`,filter:`brightness(${shade}) drop-shadow(1px 1px 1px #0006)`,offset:.70},
        {opacity:0,transform:`translate(${dx*4+12}px,${80+dy*4}px) rotate(${i*29-45}deg) scale(.12,.22)`,filter:`brightness(${shade})`}
      ],{duration:380,easing:'cubic-bezier(.35,0,.7,1)'},facet);
    }));
  }
  function save(button) {
    if (!button || reduced()) return;
    const key = button.dataset.key;
    cancel(key);
    const target = document.getElementById('scrap-open-btn');
    // All scrappable containers carry data-key, including restaurant cards.
    // Start at the parent because the bookmark button also has data-key.
    const source = button.parentElement?.closest('[data-key]') ||
      button.closest('.card,.lunch-card,.finance-news-item') || button;
    if (!target || !source.isConnected) return;
    const rect = source.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const layer = document.createElement('div');
    layer.className = 'scrap-genie';
    layer.setAttribute('aria-hidden','true');
    layer.inert = true;
    const copy = styledCopy(source,rect);
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
    // Preserve footer visibility. A temporary bookmark receives the card when
    // the footer is hidden or its button is outside the visible viewport.
    let anchor = target.getBoundingClientRect(), floating = null;
    const footerHidden = document.body.classList.contains('chrome-hidden') ||
      anchor.width <= 0 || anchor.height <= 0 || anchor.bottom <= 0 || anchor.top >= window.innerHeight;
    if (footerHidden) {
      floating = document.createElement('div');
      floating.className = 'scrap-floating-receiver';
      const viewportWidth = document.documentElement?.clientWidth || window.innerWidth;
      floating.style.left = receiverLeft(anchor, viewportWidth) + 'px';
      floating.style.right = 'auto';
      floating.setAttribute('aria-hidden','true');
      floating.inert = true;
      const footerIcon = target.querySelector('.fnav-ic svg');
      if (footerIcon) floating.appendChild(footerIcon.cloneNode(true));
      const label = document.createElement('span');
      label.className = 'scrap-floating-label';
      label.textContent = target.querySelector('.fnav-t')?.textContent.trim() || '스크랩';
      floating.appendChild(label);
      document.body.appendChild(floating);
      anchor = floating.getBoundingClientRect();
    }
    const receiver = floating || target;
    const destination = {x:anchor.left + anchor.width / 2,y:anchor.top + (floating ? 21 : Math.min(26,anchor.height / 2))};
    document.body.appendChild(layer);
    const effect = {layer,floating,raf:0,timer:0};
    active.set(key,effect);
    let start;
    const render = now => {
      if (active.get(key) !== effect) return;
      if (reduced() || !source.isConnected || !receiver.isConnected) { cancel(key); return; }
      if (start === undefined) start = now;
      const t = Math.min(1,(now-start)/520);
      slices.forEach((slice,i) => {
        const g = stripGeometry(rect,destination,t,i*step,step);
        slice.style.transform = `translate3d(${g.x}px,${g.y}px,0) scale(${g.sx},${g.sy})`;
      });
      if (t < 1) effect.raf = requestAnimationFrame(render);
      else {
        if (floating) {
          layer.remove();
          floating.classList.add('received');
          clearTimeout(effect.timer);
          effect.timer = setTimeout(() => cancel(key),320);
        } else {
          cancel(key);
          target.classList.remove('scrap-pop');
          void target.offsetWidth;
          target.classList.add('scrap-pop');
          setTimeout(() => target.classList.remove('scrap-pop'),500);
        }
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
  window.HScopeScrapMotion = {save,unsave,cancel,crumple};
})();
