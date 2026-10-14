const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/service-notice.js', 'utf8');
function setup({local = new Map(), session = new Map(), at = '2026-10-14T14:59:00Z', blocked = false} = {}) {
  const events = {}, windowEvents = {}, documentEvents = {}, classes = new Set();
  const clock = {value: Date.parse(at)};
  class ClockDate extends Date { static now() { return clock.value; } }
  const notice = {open:false, calls:0, showModal(){this.open=true;this.calls++},addEventListener(k,f){events[k]=f}};
  const prior = {isConnected:true, calls:0,focus(){this.calls++}};
  const title = {calls:0,focus(){this.calls++}};
  const checkbox = {checked:false};
  const form = {addEventListener(k,f){this[k]=f}};
  const document = {body:{},hidden:false,activeElement:prior,documentElement:{classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)}},getElementById:id=>({'service-notice':notice,'service-notice-title':title,'service-notice-form':form,'service-notice-hide-today':checkbox}[id]),addEventListener:(k,f)=>documentEvents[k]=f};
  const window = {addEventListener:(k,f)=>windowEvents[k]=f};
  const storage = values => ({getItem(k){if(blocked)throw Error('blocked');return values.get(k)||null;},setItem(k,v){if(blocked)throw Error('blocked');values.set(k,v);}});
  vm.runInNewContext(source,{document,window,Date:ClockDate,localStorage:storage(local),sessionStorage:storage(session)});
  return {notice,prior,title,events,windowEvents,documentEvents,classes,clock,local,session,checkbox,form,document};
}
test('each fresh page entry shows the notice and focuses its title',()=>{
  for(let i=0;i<2;i++){const s=setup();assert.equal(s.notice.calls,1);assert.equal(s.title.calls,1);assert.ok(s.classes.has('service-notice-open'));s.windowEvents.pageshow();assert.equal(s.notice.calls,1)}
});
test('confirmation unlocks scrolling without reopening on same-day history restoration',()=>{
 const s=setup();s.form.submit();s.notice.open=false;s.events.close();assert.equal(s.classes.size,0);assert.equal(s.prior.calls,1);s.windowEvents.pageshow({persisted:true});assert.equal(s.notice.calls,1);assert.equal(s.local.size,0);
});
test('today suppression is saved only on checked confirmation and survives app restart',()=>{
 const s=setup();s.checkbox.checked=true;assert.equal(s.local.size,0);s.form.submit();assert.equal(s.local.get('hscopeNoticeHiddenDay'),'2026-10-14');
 assert.equal(setup({local:s.local}).notice.calls,0);
 assert.equal(setup({local:s.local,at:'2026-10-14T15:00:00Z'}).notice.calls,1);
});
test('Korean midnight expires suppression even with yesterday session flag or background app',()=>{
 const s=setup();s.checkbox.checked=true;s.form.submit();s.notice.open=false;s.events.close();s.clock.value=Date.parse('2026-10-14T15:00:00Z');s.documentEvents.visibilitychange();assert.equal(s.notice.calls,2);assert.equal(s.checkbox.checked,false);
 const t=setup({local:s.local,session:new Map([['svc-notice-shown','2026-10-14']]),at:'2026-10-14T15:00:00Z'});assert.equal(t.notice.calls,1);
});
test('normal confirmation does not persist beyond a fresh app session',()=>{
 const s=setup();s.form.submit();assert.equal(setup({local:s.local}).notice.calls,1);assert.equal(setup({session:s.session}).notice.calls,0);
});
test('blocked storage still allows confirmation and same-session suppression',()=>{
 const s=setup({blocked:true});s.checkbox.checked=true;assert.doesNotThrow(()=>s.form.submit());s.notice.open=false;s.events.close();s.windowEvents.pageshow();assert.equal(s.notice.calls,1);
});
test('legacy session flag migrates to a day and no longer suppresses tomorrow',()=>{
 const s=setup({session:new Map([['svc-notice-shown','1']])});assert.equal(s.notice.calls,0);assert.equal(s.session.get('svc-notice-shown'),'2026-10-14');s.clock.value=Date.parse('2026-10-14T15:00:00Z');s.windowEvents.pageshow();assert.equal(s.notice.calls,1);
});
test('missing notice is safe and markup preserves explicit acknowledgement',()=>{
 assert.doesNotThrow(()=>vm.runInNewContext(source,{document:{getElementById:()=>null}}));
 const html=fs.readFileSync('templates/service_notice.html','utf8');assert.match(html,/method="dialog"/);assert.match(html,/type="checkbox" id="service-notice-hide-today"/);assert.equal((html.match(/service-notice-item-title/g)||[]).length,3);
});
test('escape requests explicit confirmation instead of dismissing silently',()=>{
 const s=setup();let prevented=false;s.events.cancel({preventDefault(){prevented=true}});assert.ok(prevented);assert.ok(s.notice.open);
});
