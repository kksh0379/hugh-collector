const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(horizontal=false) {
  const listeners={},classes=new Set(),scrolls=[]; let selected='';
  class Element {
    constructor(blocked=false){this.blocked=blocked;this.parentElement=null;this.scrollHeight=100;this.clientHeight=100;this.scrollWidth=100;this.clientWidth=100;this.scrollLeft=0;this.scrollTop=0;this.style={overflowX:'visible',overflowY:'visible'};}
    closest(){return this.blocked?this:null;}
    setPointerCapture(){} releasePointerCapture(){}
  }
  const root=new Element(),body=new Element(),node=new Element(),container=new Element();
  root.scrollHeight=2000;root.clientHeight=500;root.classList={add:(...cs)=>cs.forEach(c=>classes.add(c)),remove:(...cs)=>cs.forEach(c=>classes.delete(c)),toggle:(c,on)=>on?classes.add(c):classes.delete(c)};
  body.parentElement=root;node.parentElement=body;
  if(horizontal){container.scrollWidth=1000;container.clientWidth=200;container.style.overflowX='auto';container.parentElement=body;node.parentElement=container;}
  const doc={body,documentElement:root,scrollingElement:root,addEventListener:(n,f)=>listeners[n]=f};
  const win={addEventListener:(n,f)=>listeners[n]=f,getSelection:()=>({toString:()=>selected,removeAllRanges(){selected='';}}),scrollBy:o=>scrolls.push(o)};
  vm.runInNewContext(fs.readFileSync('static/js/mouse-scroll.js','utf8'),{document:doc,window:win,Element,getComputedStyle:e=>e.style,performance:{now:()=>10},Math});
  function fire(type,overrides={}) {const e={pointerType:'mouse',pointerId:1,button:0,buttons:1,target:node,clientX:50,clientY:50,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...overrides};listeners[type](e);return e;}
  return {fire,node,scrolls,classes,container,root,body,Element,select:text=>{selected=text;},selection:()=>selected};
}
test('mouse dragging scrolls opposite the hand and suppresses the resulting link click',()=>{
  const s=setup();s.fire('pointerdown');s.fire('pointermove',{clientY:30});
  assert.equal(s.scrolls[0].top,20);assert.ok(s.classes.has('mouse-scrolling'));
  s.fire('pointerup');assert.equal(s.classes.has('mouse-scrolling'),false);assert.equal(s.classes.has('mouse-scroll-pressed'),false);assert.equal(s.fire('click').prevented,true);
  s.fire('pointerdown');s.fire('pointerup');assert.equal(s.fire('click').prevented,undefined);
});
test('tiny movements keep ordinary clicks; touch, controls and shift drag stay native',()=>{
  for(const changes of [{pointerType:'touch'},{shiftKey:true}]){
    const s=setup();s.fire('pointerdown',changes);s.fire('pointermove',{clientY:10});assert.equal(s.scrolls.length,0);
  }
  const blocked=setup();blocked.node.blocked=true;blocked.fire('pointerdown');blocked.fire('pointermove',{clientY:10});assert.equal(blocked.scrolls.length,0);
  const s=setup();s.fire('pointerdown');s.fire('pointermove',{clientY:47});s.fire('pointerup');assert.equal(s.scrolls.length,0);assert.equal(s.fire('click').prevented,undefined);
});
test('horizontal lists scroll within their own container and cancellation cleans up',()=>{
  const s=setup(true);s.fire('pointerdown');s.fire('pointermove',{clientX:20});assert.equal(s.container.scrollLeft,30);assert.equal(s.scrolls.length,0);
  s.fire('pointercancel');assert.equal(s.classes.has('mouse-scrolling'),false);assert.equal(s.classes.has('mouse-scroll-pressed'),false);
});

test('existing text selection no longer blocks scrolling, and Shift still preserves it',()=>{
  const s=setup();s.select('previously selected article text');s.fire('pointerdown');
  s.fire('pointermove',{clientY:20});assert.equal(s.scrolls[0].top,30);assert.equal(s.selection(),'');
  s.fire('pointerup');s.select('keep me');s.fire('pointerdown',{shiftKey:true});
  s.fire('pointermove',{clientY:10,shiftKey:true});assert.equal(s.scrolls.length,1);assert.equal(s.selection(),'keep me');
});
test('sideways initial movement does not cancel a vertical-only gesture',()=>{
  const s=setup();s.fire('pointerdown');s.fire('pointermove',{clientX:70,clientY:48});
  assert.equal(s.scrolls.length,0);s.fire('pointermove',{clientX:72,clientY:20});
  assert.equal(s.scrolls[0].top,30);
});
test('nested vertical dialog scrolls while its locked background remains still',()=>{
  const s=setup(true);s.body.style.overflowY='hidden';
  s.container.style.overflowY='auto';s.container.scrollHeight=600;s.container.clientHeight=200;
  s.fire('pointerdown');s.fire('pointermove',{clientY:20});assert.equal(s.container.scrollTop,30);assert.equal(s.scrolls.length,0);
  s.fire('pointerup');s.node.parentElement=s.body;s.fire('pointerdown');s.fire('pointermove',{clientY:0});assert.equal(s.scrolls.length,0);
});
test('button/link surfaces accept drag while sub-threshold motion preserves a click',()=>{
  const s=setup();s.node.closest=selector=>selector.split(',').includes('button')?s.node:null;
  s.fire('pointerdown');s.fire('pointermove',{clientY:20});assert.equal(s.scrolls[0].top,30);
  s.fire('pointerup');assert.equal(s.fire('click').prevented,true);
  s.fire('pointerdown');s.fire('pointermove',{clientY:48});s.fire('pointerup');assert.equal(s.fire('click').prevented,undefined);
});
