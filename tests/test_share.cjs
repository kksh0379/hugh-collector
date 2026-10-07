const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/share.js','utf8');

function setup(navigator={}) {
  function element() {return {textContent:'',value:'',disabled:false,handlers:{},addEventListener(name, fn){this.handlers[name]=fn;},focus(){this.focused=true;},select(){this.selected=true;}};}
  const status=element(),title=element(),field=element(),close=element(),hint=element();
  const buttons=['copy','kakao','sms','other'].map(action=>({...element(),dataset:{shareAction:action},querySelector:()=>hint}));
  const dialog={...element(),open:false,querySelectorAll:()=>buttons,querySelector:()=>close,showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();},getBoundingClientRect:()=>({left:0,top:0,right:400,bottom:400})};
  const nodes={'share-dialog':dialog,'share-item-title':title,'share-url':field,'share-status':status,'share-sms':buttons[2]};
  const copied=[],shares=[];
  const ctx=vm.createContext({URL,encodeURIComponent,navigator:{userAgent:'Android',platform:'',maxTouchPoints:0,...navigator},window:{location:{}},document:{getElementById:id=>nodes[id]},copyToClipboard:async text=>{copied.push(text);return true;}});
  vm.runInContext(source,ctx);
  const trigger=element();
  return {ctx,dialog,status,title,field,buttons,copied,shares,trigger,open:(url='https://paper.example/story?a=1&b=2')=>ctx.window.HscopeShare.open(url,'한글 기사 <script>',trigger)};
}

test('share popup opens with text-safe title and exact URL, then copies it',async()=>{
  const s=setup();s.open();assert.equal(s.dialog.open,true);assert.equal(s.title.textContent,'한글 기사 <script>');
  await s.buttons[0].handlers.click();assert.deepEqual(s.copied,['https://paper.example/story?a=1&b=2']);
  assert.equal(s.status.textContent,'URL을 복사했어요.');s.dialog.close();assert.equal(s.trigger.focused,true);
});
test('kakao and iOS message actions invoke the user-controlled native share sheet',async()=>{
  const calls=[];const s=setup({userAgent:'iPhone',share:async data=>calls.push({...data})});
  s.open();await s.buttons[1].handlers.click();assert.equal(calls[0].url,'https://paper.example/story?a=1&b=2');assert.equal(calls[0].text,'한글 기사 <script>');assert.equal(s.dialog.open,false);
  s.open();await s.buttons[2].handlers.click();assert.equal(calls.length,2);assert.equal(s.ctx.window.location.href,undefined);
});
test('Android SMS composer includes encoded title and full URL without a recipient',async()=>{
  const s=setup();s.open();await s.buttons[2].handlers.click();
  const url=s.ctx.window.location.href;assert.ok(url.startsWith('sms:?body='));
  assert.equal(decodeURIComponent(url.slice('sms:?body='.length)),'한글 기사 <script>\nhttps://paper.example/story?a=1&b=2');
});
test('unsupported app sharing offers copy and cancellation leaves popup usable',async()=>{
  const unsupported=setup();unsupported.open();await unsupported.buttons[1].handlers.click();assert.match(unsupported.status.textContent,/URL 복사/);assert.equal(unsupported.dialog.open,true);
  const cancelled=setup({share:async()=>{const e=new Error();e.name='AbortError';throw e;}});cancelled.open();await cancelled.buttons[1].handlers.click();assert.equal(cancelled.dialog.open,true);assert.ok(cancelled.buttons.every(b=>!b.disabled));
});
test('invalid and credential-bearing URLs cannot be shared',()=>{
  for(const url of ['javascript:alert(1)','data:text/html,test','https://user:secret@paper.example']){const s=setup();s.open(url);assert.equal(s.dialog.open,false);}
});
