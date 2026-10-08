"use strict";
// Mouse drag scrolling complements native touch scrolling. Shift-drag selects text.
(() => {
  const excluded = 'button,input,textarea,select,label,video,audio,iframe,[role="slider"],[contenteditable]:not([contenteditable="false"]),.video-timeline,[data-mouse-scroll="off"]';
  let gesture = null, suppressUntil = 0;
  function scrollTarget(node, axis) {
    const dimension = axis === 'x' ? ['scrollWidth','clientWidth','overflowX'] : ['scrollHeight','clientHeight','overflowY'];
    for (let element = node; element && element !== document.body && element !== document.documentElement; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (/(auto|scroll|overlay)/.test(style[dimension[2]]) && element[dimension[0]] > element[dimension[1]] + 1) return element;
    }
    const page = document.scrollingElement;
    if (page && page[dimension[0]] > page[dimension[1]] + 1
        && !/(hidden|clip)/.test(getComputedStyle(document.body)[dimension[2]])
        && !/(hidden|clip)/.test(getComputedStyle(document.documentElement)[dimension[2]])) return page;
    return null;
  }
  function end(event) {
    if (!gesture || event && event.pointerId !== gesture.id) return;
    const finished = gesture; gesture = null;
    document.documentElement.classList.remove('mouse-scrolling');
    if (finished.dragging) {
      suppressUntil = performance.now() + 300;
      try { finished.capture.releasePointerCapture(finished.id); } catch (_) {}
    }
  }
  document.addEventListener('pointerdown', event => {
    suppressUntil = 0;
    if (event.pointerType !== 'mouse' || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    if (!(event.target instanceof Element) || event.target.closest(excluded)) return;
    if (window.getSelection()?.toString()) return;
    gesture = {id:event.pointerId, node:event.target, capture:event.target, x:event.clientX, y:event.clientY, dragging:false};
  }, true);
  document.addEventListener('pointermove', event => {
    if (!gesture || event.pointerId !== gesture.id) return;
    if (!(event.buttons & 1)) { end(event); return; }
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    if (!gesture.dragging) {
      if (Math.hypot(dx,dy) < 8) return;
      gesture.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      gesture.scroller = scrollTarget(gesture.node,gesture.axis);
      if (!gesture.scroller) { gesture=null; return; }
      gesture.dragging = true;
      document.documentElement.classList.add('mouse-scrolling');
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
