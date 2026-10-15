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
  function crumpleGeometry(rect, viewport) {
    const left = rect.left || 0, top = rect.top || 0;
    const visibleLeft = Math.max(0,left), visibleRight = Math.min(viewport.width,left+rect.width);
    const available = Math.max(0,visibleRight-visibleLeft), width = Math.min(420,available);
    const stageLeft = visibleLeft-left+(available-width)/2;
    const size = Math.min(40,width*.16);
    const ballLeft = stageLeft+Math.min(24,width*.08), binLeft = stageLeft+width-70;
    const visibleTop = Math.max(0,top), visibleBottom = Math.min(viewport.height,top+rect.height);
    const centerY = Math.max(80,Math.min(viewport.height-120,(visibleTop+visibleBottom)/2))-top;
    const hitX = Math.max(0,binLeft-10-ballLeft-size/2);
    return {size,ballLeft,binLeft,centerY,hitX,arc:Math.min(54,hitX*.3),rebound:Math.min(80,hitX*.65)};
  }
  function floorBouncePlan({hitX,arc,rebound,size}) {
    const start = 420, travel = Math.max(640,hitX/220*1000);
    const hops = Math.max(2,Math.min(4,Math.round(hitX/85)));
    const hitTime = start+travel, duration = hitTime+350, samples = [];
    const add = (time,x,y,sx,sy,rotation,opacity=1) => samples.push({time,x,y,sx,sy,rotation,opacity});
    add(0,0,0,1.65,1.35,-14,0); add(220,0,0,1.5,1.28,-14,0);
    add(300,0,0,1.22,.95,9,.7); add(380,0,0,.86,1.06,-11);
    const floor = 54, restingY = floor-size/2;
    add(start,0,floor-size*.76/2,1.12,.76,7);
    const floorHits = [{time:start,x:0}];
    for (let hop=0;hop<hops;hop++) {
      const height = arc*(1-hop*.18);
      for (let step=1;step<=10;step++) {
        const u = step/10, landed = step===10, last = hop===hops-1 && landed;
        const sx = last ? .55 : landed ? 1.12 : .94, sy = last ? 1.14 : landed ? .76 : 1.04;
        const x = hitX*(hop+u)/hops, y = landed ? floor-size*sy/2 : restingY-4*height*u*(1-u);
        add(start+travel*(hop+u)/hops,x,y,sx,sy,120*(hop+u));
      }
      if (hop<hops-1) floorHits.push({time:start+travel*(hop+1)/hops,x:hitX*(hop+1)/hops});
    }
    add(hitTime+50,hitX,34,.72,1.05,120*hops);
    add(hitTime+200,hitX-rebound*.525,-arc*.445,1.04,.9,120*hops-60);
    add(hitTime+290,hitX-rebound*.85,-arc*.093,.95,.95,120*hops-100,.9);
    add(duration,hitX-rebound,36,.9,.9,120*hops-125,0);
    return {duration,hitTime,travel,hops,floorHits,samples,frames:samples.map(p=>({
      opacity:p.opacity,offset:p.time/duration,
      transform:`translate(${p.x}px,${p.y}px) scale(${p.sx},${p.sy}) rotate(${p.rotation}deg)`
    }))};
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
  function paperBallMarkup() {
    // Original vector artwork: uneven silhouette, broad paper shadows, narrow doubled creases.
    return `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M30 8 Q38 1 47 8 L57 5 Q67 4 71 14 L80 16 Q87 20 86 29 L93 39 Q99 49 92 56 L94 65 Q91 74 81 76 L77 87 Q70 94 60 90 L50 95 Q41 97 34 89 L24 87 Q15 85 16 74 L7 66 Q1 57 8 48 L5 37 Q7 28 18 26 L19 17 Z" fill="#f4f1e9" stroke="#d0ccc3" stroke-width="1.2"/>
      <path d="M30 8 35 30 19 17 18 26 27 43 8 48 25 52 16 74 34 63 34 89 45 72 60 90 58 68 81 76 70 59 92 56 75 44 86 29 65 33 71 14 51 29 47 8 44 31 Z" fill="#c1bdb4" opacity=".55"/>
      <path d="m35 30 9 1 7-2 14 4-10 10 20 1-17 10 12 5-12 9-13 4-11-9-9-11 2-9Z" fill="#fffcf5"/>
      <path d="m30 8 5 22 9 1-6-15Z m37 35 18 0-9 12-12 8Z m58 54 17-10-5 15Z m34 63 11 9-11 17Z m26 78-10-4 9-22 5 11Z" fill="#aaa79f" opacity=".4"/>
      <g fill="none" stroke="#a6a39c" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round" opacity=".85">
        <path d="m27 16 8 14-5 9 7 4-5 11 2 9-8 15"/>
        <path d="m53 13-2 16 8 6-4 8 8 7-5 4 2 11-2 3 5 14"/>
        <path d="m14 36 13 7 10 0 9 6 9-6 10-10 14-7"/>
        <path d="m14 61 11-9 7 2 12 5 2-10 12 5 12 5 12 7"/>
        <path d="m44 31-7 12 m7 16 1 13 6 12 m-11-17-6-4 m36-4 5-15 10 1"/>
      </g>
      <g fill="none" stroke="#fffef9" stroke-width="1.8" stroke-linecap="round" opacity=".95">
        <path d="m29 17 8 13-5 9 7 4-5 11 2 9"/>
        <path d="m55 14-2 15 8 6-4 8 8 7-5 4"/>
        <path d="m16 35 13 7 10 0 8 5 8-6 10-10"/>
        <path d="m16 62 10-8 7 2 9 5 m5 2 0 9 6 11"/>
      </g>
      <path d="m24 31 4 3-1 5 m45-16-6 4 2 5 m-4 43-5-4-4 3 m26-17-5-3" fill="none" stroke="#b9b5ab" stroke-width=".8"/>
    </svg>`;
  }
  async function crumple(card, play) {
    const rect = card.getBoundingClientRect();
    const copy = styledCopy(card,rect);
    const surface = document.createElement('div');
    surface.className = 'scrap-crumple-surface';
    surface.setAttribute('aria-hidden','true'); surface.inert = true;
    const edge = [[0,0],[30,0],[66,0],[100,0],[100,31],[100,68],[100,100],[69,100],[34,100],[0,100],[0,69],[0,32]];
    const facets = edge.map((p,i) => {
      const q = edge[(i+1)%edge.length];
      const facet = document.createElement('div');
      facet.className = 'scrap-paper-facet';
      facet.style.clipPath = `polygon(48% 52%,${p[0]}% ${p[1]}%,${q[0]}% ${q[1]}%)`;
      facet.appendChild(copy.cloneNode(true));surface.appendChild(facet);return facet;
    });
    const ball = document.createElement('div');
    ball.className = 'scrap-paper-ball'; ball.innerHTML = paperBallMarkup();
    const {size,ballLeft,binLeft,centerY,hitX,arc,rebound} = crumpleGeometry(rect,{
      width:document.documentElement?.clientWidth || window.innerWidth || rect.width,
      height:window.innerHeight || 800
    });
    const foldLeft = ballLeft+size/2-rect.width/2;
    const foldTop = centerY-rect.height/2;
    Object.assign(ball.style,{width:size+'px',height:size+'px',left:ballLeft+'px',top:(centerY-size/2)+'px'});
    surface.appendChild(ball);
    const bin = document.createElement('div');
    bin.className = 'scrap-trash-bin';
    bin.innerHTML = `<svg viewBox="0 0 54 66" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="27" cy="14" rx="19" ry="6" fill="#253144" stroke="#8fa6c7" stroke-width="1.6"/>
      <g class="scrap-trash-filled-paper">
        ${paperBallMarkup().replace('<svg ', '<svg x="27" y="-1" width="21" height="23" ')}
        ${paperBallMarkup().replace('<svg ', '<svg x="10" y="-10" width="30" height="32" ')}
      </g>
      <path d="M8 15 Q27 23 46 15 L42 57 Q27 65 12 57 Z" fill="#758ba9" stroke="#bdd0ec" stroke-width="1.7"/>
      <path d="M17 29 19 53 M27 30V56 M37 29 35 53" fill="none" stroke="#d3dff0" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
    Object.assign(bin.style,{left:binLeft+'px',top:(centerY-12)+'px'});
    surface.appendChild(bin);
    const impact = document.createElement('div');
    impact.className = 'scrap-bounce-impact';
    impact.innerHTML = `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="24" cy="24" r="13" fill="none" stroke="#b9d7ff" stroke-width="1.8"/><path d="M24 3V10 M24 38V45 M3 24H10 M38 24H45 M9 9 14 14 M34 34 39 39 M9 39 14 34 M34 14 39 9" fill="none" stroke="#d9eaff" stroke-width="2.8" stroke-linecap="round"/><path d="m24 16 2 6 6 2-6 2-2 6-2-6-6-2 6-2Z" fill="#ffe1a0"/></svg>`;
    Object.assign(impact.style,{left:(binLeft-19)+'px',top:(centerY+10)+'px'});
    surface.appendChild(impact);
    card.appendChild(surface);card.classList.add('scrap-crumpling');
    const plan = floorBouncePlan({hitX,arc,rebound,size});
    const {duration,hitTime} = plan;
    const at = ms => ms/duration;
    const folds = facets.map((facet,i) => {
      const angle = i*Math.PI/6, dx=Math.cos(angle),dy=Math.sin(angle);
      const shade=i%3===0?'.64':i%3===1?'1.3':'.9';
      return play([
        {opacity:1,transform:'none',filter:'brightness(1)'},
        {opacity:1,transform:`translate(${dx*-9}px,${dy*-7}px) perspective(460px) rotateX(${dy*42}deg) rotateY(${-dx*48}deg) skew(${i%2?12:-15}deg) scale(.78,.83)`,filter:`brightness(${shade})`,offset:.22},
        {opacity:1,transform:`translate(${foldLeft*.55+dx*7}px,${foldTop*.55+dy*9}px) rotate(${i%2?30:-24}deg) skew(${i%2?-18:14}deg) scale(.38,.49)`,filter:`brightness(${shade}) drop-shadow(2px 1px 2px #0006)`,offset:.36},
        {opacity:.35,transform:`translate(${foldLeft+dx*5}px,${foldTop+dy*4}px) rotate(${i*23-90}deg) scale(.15,.23)`,filter:`brightness(${shade})`,offset:.43},
        {opacity:0,transform:`translate(${foldLeft+dx*3}px,${foldTop+dy*2}px) rotate(${i*23-74}deg) scale(.10,.16)`,offset:.50},
        {opacity:0,transform:'scale(.1)'}
      ],{duration:760,easing:'linear'},facet);
    });
    folds.push(play(plan.frames,{duration,easing:'linear'},ball));
    folds.push(play([
      {opacity:0,transform:'translateY(6px) scale(.85)',offset:0},
      {opacity:0,transform:'translateY(6px) scale(.85)',offset:at(160)},
      {opacity:1,transform:'none',offset:at(320)},
      {opacity:1,transform:'none',offset:at(hitTime)},
      {opacity:1,transform:'translateX(5px) rotate(9deg)',offset:at(hitTime+40)},
      {opacity:1,transform:'rotate(-4deg)',offset:at(hitTime+120)},
      {opacity:1,transform:'none',offset:at(duration-40)},
      {opacity:0,transform:'none',offset:1}
    ],{duration,easing:'linear'},bin));
    folds.push(play([
      {opacity:0,transform:'scale(.4)',offset:0},
      {opacity:0,transform:'scale(.4)',offset:at(hitTime-5)},
      {opacity:1,transform:'scale(.65)',offset:at(hitTime+10)},
      {opacity:.9,transform:'scale(1.15)',offset:at(hitTime+90)},
      {opacity:0,transform:'scale(1.55)',offset:at(hitTime+210)},
      {opacity:0,transform:'scale(1.55)',offset:1}
    ],{duration,easing:'linear'},impact));
    const ground = document.createElement('div');
    ground.className = 'scrap-bounce-ground';
    Object.assign(ground.style,{left:(ballLeft-8)+'px',top:(centerY+54)+'px',width:(binLeft+62-ballLeft)+'px'});
    surface.appendChild(ground);
    folds.push(play([{opacity:0,offset:0},{opacity:.65,offset:at(380)},
      {opacity:.65,offset:at(duration-80)},{opacity:0,offset:1}],{duration,easing:'linear'},ground));
    plan.floorHits.forEach(hit => {
      const pulse = document.createElement('div'); pulse.className = 'scrap-floor-pulse';
      Object.assign(pulse.style,{left:(ballLeft+size/2+hit.x-14)+'px',top:(centerY+49)+'px'});
      surface.appendChild(pulse);
      folds.push(play([
        {opacity:0,transform:'scale(.4)',offset:0},
        {opacity:0,transform:'scale(.4)',offset:at(hit.time-2)},
        {opacity:1,transform:'scale(.75)',offset:at(hit.time+12)},
        {opacity:0,transform:'scale(1.65)',offset:at(hit.time+160)},
        {opacity:0,transform:'scale(1.65)',offset:1}
      ],{duration,easing:'linear'},pulse));
    });
    await Promise.all(folds);
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
