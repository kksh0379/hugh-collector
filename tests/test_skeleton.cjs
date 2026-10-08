const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const skeleton=fs.readFileSync('static/js/skeleton.js','utf8');
function context(extra={}){const ctx=vm.createContext({window:{},...extra});vm.runInContext(skeleton,ctx);ctx.HScopeSkeleton=ctx.window.HScopeSkeleton;return ctx;}
function node(tagName='DIV'){return {tagName,innerHTML:'',children:[],attrs:{},textContent:'',append(n){this.children.push(n);},replaceChildren(){this.children=[];this.innerHTML='';},setAttribute(k,v){this.attrs[k]=v;},querySelector(){return this.innerHTML.includes('hs-skeleton')?{}:null;}};}
test('loading markup is local, noninteractive and escapes status text',()=>{
 const ctx=context();const html=ctx.HScopeSkeleton.html('card',{count:3,list:true,label:'<img onerror=alert(1)>'});
 assert.equal((html.match(/<li /g)||[]).length,3);assert.equal((html.match(/role="status"/g)||[]).length,1);
 assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img|<button|<a /);assert.match(html,/aria-hidden="true"/);
 const target=node('UL');ctx.HScopeSkeleton.render(target,'food');assert.match(target.innerHTML,/^<li /);
});
test('a news refresh preserves an existing card; initial load displays a skeleton',()=>{
 const source=fs.readFileSync('static/js/app.js','utf8'),ctx=context();
 vm.runInContext(source.slice(source.indexOf('function showLoading'),source.indexOf('// 리스트 엘리먼트')),ctx);
 const loaded={innerHTML:'existing',querySelector:()=>({})};ctx.showLoading(loaded);assert.equal(loaded.innerHTML,'existing');
 const fresh=node('UL');fresh.id='list-cat';ctx.showLoading(fresh);assert.match(fresh.innerHTML,/hs-sk-card/);
});
function reader(){const body=node(),retry={hidden:true},ctx=context({body,retry,status:node(),title:node(),meta:node(),source:node(),dialog:{open:true},controller:null,summaryController:null,sequence:0,AbortController,setTimeout:()=>1,clearTimeout:()=>{},document:{createElement:()=>node()},loadSummary(){},safeUrl:x=>x});const src=fs.readFileSync('static/js/reader.js','utf8');vm.runInContext(src.slice(src.indexOf('  async function load('),src.indexOf('  function showSummary')),ctx);return ctx;}
test('reader replaces the skeleton with paragraphs and removes it after failure',async()=>{
 const ctx=reader();let resolve;ctx.fetch=()=>new Promise(r=>resolve=r);const request=ctx.load('https://example.test/1');assert.match(ctx.body.innerHTML,/hs-sk-reader/);assert.equal(ctx.body.attrs['aria-busy'],'true');
 resolve({ok:true,json:async()=>({title:'제목',paragraphs:['본문 A','본문 B']})});await request;assert.equal(ctx.body.innerHTML,'');assert.equal(ctx.body.children.length,2);assert.equal(ctx.body.attrs['aria-busy'],'false');
 ctx.fetch=async()=>{throw Error('offline');};await ctx.load('https://example.test/2');assert.equal(ctx.body.innerHTML,'');assert.equal(ctx.body.children.length,0);assert.equal(ctx.retry.hidden,false);
});
test('a stale reader failure cannot erase the next article loading state',async()=>{
 const ctx=reader(),pending=[];ctx.fetch=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}));const first=ctx.load('https://example.test/old');const next=ctx.load('https://example.test/new');pending[0].reject(Error('old failure'));await first;assert.match(ctx.body.innerHTML,/hs-sk-reader/);assert.equal(ctx.body.attrs['aria-busy'],'true');pending[1].resolve({ok:true,json:async()=>({title:'새 기사',paragraphs:['새 본문']})});await next;assert.equal(ctx.body.children[0].textContent,'새 본문');
});
test('finance failure and exhausted polling remove pending skeletons',async()=>{
 for(const fail of [true,false]){const els=Object.fromEntries(['finance-news','finance-indicators','finance-status'].map(k=>[k,node()]));const ctx=context({$:id=>els[id],loading:false,data:null,json:async()=>{if(fail)throw Error('offline');return {pending:true};},render(){},pause:async()=>{}});ctx.loadingHtml=()=>ctx.HScopeSkeleton.html('card');const src=fs.readFileSync('static/js/finance.js','utf8');vm.runInContext(src.slice(src.indexOf('  async function load()'),src.indexOf('  async function loadStock()')),ctx);await ctx.load();assert.doesNotMatch(els['finance-news'].innerHTML,/hs-skeleton/);assert.doesNotMatch(els['finance-indicators'].innerHTML,/hs-skeleton/);assert.equal(ctx.loading,false);}
});
test('finance suppresses legacy demo values, change and charts while keeping live observations',()=>{
 const ctx=vm.createContext({esc:String,fmtDate:String,modes:{unconfigured:'연결 준비',live:'실데이터'}});
 const src=fs.readFileSync('static/js/finance.js','utf8');
 vm.runInContext(src.slice(src.indexOf('  function indicatorCardHtml('),src.indexOf('  function render(result)')),ctx);
 const sample={name:'환율',code:'ECOS/USD',unit:'원',value:98765,change:12345,ratio:99,date:'20990101',mode:'demo',history:[{value:1},{value:2}]};
 const html=ctx.indicatorCardHtml(sample);
 assert.match(html,/연결 준비/);assert.match(html,/<strong>—<\/strong>/);assert.doesNotMatch(html,/98,765|12345|20990101|<svg/);
 const live=ctx.indicatorCardHtml({...sample,mode:'live'});assert.match(live,/98,765/);assert.match(live,/<svg/);
});
