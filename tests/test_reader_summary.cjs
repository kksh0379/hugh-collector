const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/reader.js','utf8');
const helpers = source.slice(source.indexOf('  function showSummary'),source.indexOf('  summaryButton.addEventListener'));
function node() {return {children:[],textContent:'',append(c){this.children.push(c);},replaceChildren(){this.children=[];},setAttribute(){},set innerHTML(v){throw Error('summary must not insert HTML');}};}
test('a late summary cannot replace the next article and summary strings remain text',async()=>{
  const pending=[], status=node();
  const ctx=vm.createContext({status,sequence:1,dialog:{open:true},AbortController,
    setTimeout:()=>1,clearTimeout:()=>{},document:{createElement:()=>node()},
    fetch:()=>new Promise(resolve=>pending.push(resolve))});
  vm.runInContext(helpers,ctx);
  const first=ctx.loadSummary('https://publisher.example/old',1);
  ctx.sequence=2;
  const second=ctx.loadSummary('https://publisher.example/new',2);
  pending[1]({ok:true,json:async()=>({status:'ready',points:['새 기사 요약','<img src=x onerror=alert(1)>']})});
  await second;
  pending[0]({ok:true,json:async()=>({status:'ready',points:['이전 기사 요약','이전 기사 내용']})});
  await first;
  assert.equal(status.children[1].children[0].textContent,'새 기사 요약');
  assert.equal(status.children[1].children[1].textContent,'<img src=x onerror=alert(1)>');
});
test('summary failure leaves a readable message in the summary box',async()=>{
  const status=node();
  const ctx=vm.createContext({status,sequence:1,dialog:{open:true},AbortController,setTimeout:()=>1,clearTimeout:()=>{},document:{createElement:()=>node()},fetch:async()=>{throw Error('offline');}});
  vm.runInContext(helpers,ctx);
  await ctx.loadSummary('https://publisher.example/1',1);
  assert.match(status.children[1].textContent,/본문은 아래에서 읽을 수/);
});
test('key phrases become strong text nodes and the sentence stays intact',()=>{
  const item=node();
  const ctx=vm.createContext({document:{createElement:()=>node(),createTextNode:text=>({textContent:text})}});
  vm.runInContext(helpers,ctx);
  const point='기관은 10만 건 유출을 확인하고 비밀번호 변경을 권고했습니다.';
  ctx.appendSummaryHighlights(item,point,['비밀번호 변경','10만 건','없는 내용']);
  assert.equal(item.children.map(c=>c.textContent).join(''),point);
  assert.deepEqual(item.children.filter(c=>c.className==='reader-summary-key').map(c=>c.textContent),['10만 건','비밀번호 변경']);
});
test('invalid, overlapping and excessive highlighting stays bounded',()=>{
  const item=node();
  const ctx=vm.createContext({document:{createElement:()=>node(),createTextNode:text=>({textContent:text})}});
  vm.runInContext(helpers,ctx);
  const point='기관은 개인정보 보호 조치를 강화하고 관련 절차를 점검했습니다.';
  ctx.appendSummaryHighlights(item,point,[point,'개인정보 보호','개인정보','관련 절차','기관']);
  assert.equal(item.children.map(c=>c.textContent).join(''),point);
  assert.deepEqual(item.children.filter(c=>c.className==='reader-summary-key').map(c=>c.textContent),['개인정보 보호','관련 절차']);
});

test('saved-information summaries show one point and their limited source explicitly',async()=>{
  const status=node();
  const ctx=vm.createContext({status,sequence:1,dialog:{open:true},AbortController,setTimeout:()=>1,clearTimeout:()=>{},document:{createElement:()=>node()},fetch:async()=>({ok:true,json:async()=>({status:'ready',source_kind:'excerpt',points:['기관이 새 프로그램 참여자를 모집합니다.'],highlights:[[]]})})});
  vm.runInContext(helpers,ctx);
  await ctx.loadSummary('https://publisher.example/1',1);
  assert.equal(status.children[0].textContent,'AI 요약 · 수집 정보 기준');
  assert.equal(status.children[1].children.length,1);
  assert.match(status.children[2].textContent,/원문 전체를 확보하지 못해/);
});
test('loading an article never starts AI; only the manual control invokes it',()=>{
  const load=source.slice(source.indexOf('  async function load('),source.indexOf('  function showSummary'));
  assert.doesNotMatch(load,/loadSummary\(/);
  const click=source.slice(source.indexOf('  summaryButton.addEventListener'),source.indexOf('  document.addEventListener'));
  assert.match(click,/summaryButton.disabled \|\| !dialog.open/);
  assert.match(click,/await loadSummary\(activeUrl, current\)/);
});

test('opening fetches only body; manual clicks deduplicate and reopening resets the control',async()=>{
  const nodes=new Map(),events={},requests=[],pending=[];
  function element(){return {hidden:false,disabled:false,style:{},children:[],attrs:{},textContent:'',isConnected:true,setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this[k]=f;},append(c){this.children.push(c);},replaceChildren(){this.children=[];},focus(){},showModal(){this.open=true;},close(){this.open=false;}};}
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:()=>element(),createTextNode:t=>({textContent:t}),addEventListener:(k,f)=>events[k]=f,querySelectorAll:()=>[],body:{style:{}}};
  const context={document,window:{},URL,AbortController,HScopeSkeleton:{render(){}},setTimeout:()=>1,clearTimeout(){},fetch:async(url)=>{
    requests.push(url);
    if(url.startsWith('/api/reader-summary'))return new Promise(resolve=>pending.push(resolve));
    return {ok:true,json:async()=>({title:'기사',paragraphs:['본문'],mode:'article'})};
  }};
  vm.runInNewContext(source,context);
  const dialog=nodes.get('reader-view'),button=nodes.get('reader-summary-button');
  function open(url){const link={href:url,isConnected:true,closest:()=>null,focus(){}};events.click({target:{closest:()=>link},button:0,preventDefault(){}});}
  open('https://example.com/1');await new Promise(setImmediate);
  assert.equal(requests.length,1);assert.equal(button.disabled,false);assert.equal(nodes.get('reader-status').hidden,true);
  const first=button.click();button.click();assert.equal(requests.length,2);assert.equal(button.disabled,true);
  pending.shift()({ok:true,json:async()=>({status:'ready',points:['수동 요약']})});await first;assert.equal(button.hidden,true);
  open('https://example.com/2');await new Promise(setImmediate);assert.equal(button.hidden,false);assert.equal(button.disabled,false);assert.equal(requests.length,3);
  const second=button.click();dialog.open=false;dialog.close();pending.shift()({ok:true,json:async()=>({status:'ready',points:['늦은 요약']})});await second;
  assert.equal(nodes.get('reader-status').children.length,2); // only the pending heading and note remain
});
