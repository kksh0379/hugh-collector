const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('vm'),fs=require('fs');
const source=fs.readFileSync('static/js/scrap-undo.js','utf8');
function setup(){
 const panels=[],timers=new Map(),clock={now:0};let id=0;
 function node(){return {children:[],attrs:{},removed:false,setAttribute(k,v){this.attrs[k]=v},appendChild(c){this.children.push(c)},addEventListener(k,f){this[k]=f},remove(){this.removed=true}};}
 const window={innerHeight:800};const document={createElement:()=>node(),body:{appendChild:n=>panels.push(n)}};
 vm.runInNewContext(source,{window,document,Date:{now:()=>clock.now},setTimeout:(fn,ms)=>{timers.set(++id,{fn,ms});return id},clearTimeout:i=>timers.delete(i)});
 return {api:window.HScopeScrapUndo,panels,timers,clock};
}
const record=key=>({key,user:'alice',generation:1,snapshot:{key,ts:100,groups:['group-one'],title:'Saved'}});
test('undo within five seconds restores a deep copy with original groups and timestamp',()=>{
 const s=setup(),calls=[],saved=record('a');s.api.show(saved,r=>calls.push(r));saved.snapshot.groups.push('changed');
 const panel=s.panels[0];assert.equal(panel.children[1].textContent,'실행 취소 (1)');assert.equal([...s.timers.values()][0].ms,5000);
 s.clock.now=4999;panel.children[1].click();assert.equal(calls.length,1);assert.equal(calls[0].snapshot.ts,100);assert.deepEqual([...calls[0].snapshot.groups],['group-one']);assert(panel.removed);assert.equal(s.timers.size,0);
});
test('expired undo cannot restore and removes the notice',()=>{
 const s=setup();let calls=0;s.api.show(record('a'),()=>calls++);s.clock.now=5001;s.panels[0].children[1].click();assert.equal(calls,0);assert(s.panels[0].removed);
});
test('only the latest cancellation is actionable and a stale click cannot clear it',()=>{
 const s=setup(),calls=[];s.api.show(record('a'),r=>calls.push(r.key));s.api.show(record('b'),r=>calls.push(r.key));
 assert(s.panels[0].removed);s.panels[0].children[1].click();assert(!s.panels[1].removed);s.panels[1].children[1].click();assert.deepEqual(calls,['b']);
});
test('timeout and keyed cleanup remove only the matching cancellation',()=>{
 const s=setup();s.api.show(record('a'),()=>{});s.api.clear('b');assert(!s.panels[0].removed);[...s.timers.values()][0].fn();assert(s.panels[0].removed);
 s.api.show(record('b'),()=>{});s.api.clear();assert(s.panels[1].removed);
});
test('only three recent cancellations are kept and repeated undo restores newest first',()=>{
 const s=setup(),calls=[];
 for(const key of ['a','b','c','d']) s.api.show(record(key),r=>calls.push(r.key));
 assert.equal(s.panels.at(-1).children[1].textContent,'실행 취소 (3)');
 s.clock.now=4900;s.panels.at(-1).children[1].click();
 assert.equal(s.panels.at(-1).children[1].textContent,'실행 취소 (2)');
 s.clock.now=9000;s.panels.at(-1).children[1].click();
 s.panels.at(-1).children[1].click();assert.deepEqual(calls,['d','c','b']);assert(s.panels.at(-1).removed);assert.equal(s.timers.size,0);
});
test('clearing one failed or resaved item preserves the other undo records',()=>{
 const s=setup(),calls=[];
 for(const key of ['a','b','c']) s.api.show(record(key),r=>calls.push(r.key));
 s.api.clear('b');assert.equal(s.panels.at(-1).children[1].textContent,'실행 취소 (2)');
 s.panels.at(-1).children[1].click();s.panels.at(-1).children[1].click();assert.deepEqual(calls,['c','a']);
});
test('duplicate keys and changed accounts cannot retain stale restoration records',()=>{
 const s=setup(),calls=[];
 s.api.show(record('a'),r=>calls.push(r.key));s.api.show(record('a'),r=>calls.push(r.key));assert.equal(s.panels.at(-1).children[1].textContent,'실행 취소 (1)');
 s.api.show({...record('b'),user:'bob'},r=>calls.push(r.key));s.panels.at(-1).children[1].click();assert.deepEqual(calls,['b']);
});
function card(key,top=200){
 const classes=new Set(),scrolls=[];
 return {dataset:{key},style:{},classes,scrolls,classList:{add:k=>classes.add(k),remove:k=>classes.delete(k)},getBoundingClientRect:()=>({top,bottom:top+150}),scrollIntoView:opts=>scrolls.push(opts)};
}
const list=cards=>({closest:()=>null,querySelectorAll:()=>cards});
test('restoration highlights only the restored card, brings an offscreen card into view and cleans up',()=>{
 const s=setup(),a=card('a'),b=card('b',1200);s.api.markRestored('b');s.api.animateRestored(list([a,b]));
 assert(!a.classes.size);assert(b.classes.has('scrap-restored'));assert.equal(b.scrolls.length,1);assert.equal(b.scrolls[0].block,'center');
 [...s.timers.values()][0].fn();assert(!b.classes.size);assert.equal(b.style.animationDelay,'');
});
test('a delayed render still highlights restoration and a server rerender resumes without scrolling twice',()=>{
 const s=setup();s.api.markRestored('a');s.api.animateRestored(list([]));s.clock.now=400;
 const a=card('a');s.api.animateRestored(list([a]));assert(a.classes.has('scrap-restored'));assert.equal(a.scrolls.length,0);
 s.clock.now=650;const replacement=card('a',1200);s.api.animateRestored(list([replacement]));assert.equal(replacement.style.animationDelay,'-250ms');assert.equal(replacement.scrolls.length,0);
 s.clock.now=1400;const late=card('a');s.api.animateRestored(list([late]));assert(!late.classes.size);
});
test('rapid undo highlights each restored card even when their renders are delayed together',()=>{
 const s=setup(),a=card('a'),b=card('b');s.api.markRestored('a');s.api.markRestored('b');
 s.api.animateRestored(list([a,b]));assert(a.classes.has('scrap-restored'));assert(b.classes.has('scrap-restored'));
});
