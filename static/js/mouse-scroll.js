"use strict";
// Left-button drag pans content. Shift-drag retains native text selection.
(() => {
  const excluded = 'input,textarea,select,video,audio,iframe,[role="slider"],[contenteditable]:not([contenteditable="false"]),.video-timeline,[data-mouse-scroll="off"]';
  const root = document.documentElement;
  let gesture = null, suppressUntil = 0;
  function scrollTarget(node, axis) {
    const dimension = axis === 'x' ? ['scrollWidth','clientWidth','overflowX'] : ['scrollHeight','clientHeight','overflowY'];
    for (let element = node; element && element !== document.body && element !== root; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (/(auto|scroll|overlay)/.test(style[dimension[2]]) && element[dimension[0]] > element[dimension[1]] + 1) return element;
    }
    const page = document.scrollingElement;
    if (page && page[dimension[0]] > page[dimension[1]] + 1
        && !/(hidden|clip)/.test(getComputedStyle(document.body)[dimension[2]])
        && !/(hidden|clip)/.test(getComputedStyle(root)[dimension[2]])) return page;
    return null;
  }
  function eligible(node) {
    return node instanceof Element && !node.closest(excluded);
  }
  function hover(event) {
    if (gesture) return;
    const node = event.target;
    const ready = event.pointerType === 'mouse' && !event.shiftKey && eligible(node)
      && (scrollTarget(node,'y') || scrollTarget(node,'x'));
    root.classList.toggle('mouse-scroll-ready',!!ready);
  }
  function end(event) {
    if (!gesture || event && event.pointerId !== gesture.id) return;
    const finished = gesture; gesture = null;
    root.classList.remove('mouse-scrolling','mouse-scroll-pressed');
    if (finished.dragging) {
      suppressUntil = performance.now() + 300;
      try { finished.capture.releasePointerCapture(finished.id); } catch (_) {}
    }
    if (event) hover(event);
    else root.classList.remove('mouse-scroll-ready');
  }
  document.addEventListener('pointerover',hover,true);
  document.addEventListener('pointerdown', event => {
    suppressUntil = 0;
    if (event.pointerType !== 'mouse' || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    if (!eligible(event.target)) return;
    const xTarget = scrollTarget(event.target,'x'), yTarget = scrollTarget(event.target,'y');
    if (!xTarget && !yTarget) return;
    // Existing selected text must not disable the next scrolling gesture.
    gesture = {id:event.pointerId, node:event.target, capture:event.target, x:event.clientX, y:event.clientY, xTarget,yTarget, dragging:false};
    root.classList.add('mouse-scroll-pressed');
  }, true);
  document.addEventListener('pointermove', event => {
    if (!gesture || event.pointerId !== gesture.id) { hover(event); return; }
    if (!(event.buttons & 1)) { end(event); return; }
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    if (!gesture.dragging) {
      if (Math.hypot(dx,dy) < 6) return;
      let axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      if (!gesture[axis+'Target']) axis = axis === 'x' ? 'y' : 'x';
      // Wait for movement along the available axis instead of cancelling on sideways jitter.
      if (Math.abs(axis === 'x' ? dx : dy) < 6) return;
      gesture.axis = axis;
      gesture.scroller = gesture[axis+'Target'];
      gesture.dragging = true;
      root.classList.add('mouse-scrolling');
      window.getSelection()?.removeAllRanges();
      try { gesture.capture.setPointerCapture(gesture.id); } catch (_) {}
    }
    event.preventDefault();
    if (gesture.scroller === document.scrollingElement) {
      window.scrollBy({left:gesture.axis === 'x' ? -dx : 0, top:gesture.axis === 'y' ? -dy : 0, behavior:'instant'});
    } else {
      if (gesture.axis === 'x') gesture.scroller.scrollLeft -= dx;
      else gesture.scroller.scrollTop -= dy;
    }
    gesture.x=event.clientX;gesture.y=event.clientY;
  }, {capture:true,passive:false});
  document.addEventListener('pointerup',end,true);
  document.addEventListener('pointercancel',end,true);
  document.addEventListener('lostpointercapture',end,true);
  window.addEventListener('blur',()=>end());
  document.addEventListener('dragstart',event=>{if(gesture)event.preventDefault();},true);
  document.addEventListener('click',event=>{
    if (performance.now() < suppressUntil) {event.preventDefault();event.stopImmediatePropagation();suppressUntil=0;}
  },true);
})();
