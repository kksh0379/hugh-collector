const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/healthchecks.js','utf8');
async function screen(report){
  const elements=new Map();
  const el=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',checked:false,open:false,hidden:false,disabled:false,value:'',addEventListener(name,fn){this[name]=fn},querySelectorAll(){return []},showModal(){this.open=true},close(){this.open=false}});return elements.get(id)};
  const context={document:{getElementById:el,body:{classList:{contains:()=>true}}},MutationObserver:class{observe(){}},AbortController,Date,fetch:async()=>({ok:true,json:async()=>({report,history:report?[{...report,trigger:'manual'}]:[]})}),setTimeout:()=>1,clearTimeout(){},setInterval(){}};
  vm.runInNewContext(source,context);el('healthchecks-btn').click();await new Promise(setImmediate);return el;
}
test('completed total, individual duration and history survive result rendering',async()=>{
  const el=await screen({id:'stored',started_at:'2026-10-09T03:00:00+09:00',finished_at:'2026-10-09T03:02:05+09:00',duration_ms:125000,status:'passed',results:[{group:'영상',name:'회차',status:'passed',detail:'정상',duration_ms:1320}]});
  assert.match(el('healthcheck-timing').innerHTML,/총 소요 시간[\s\S]*2분 5초/);
  assert.match(el('healthcheck-results').innerHTML,/<time>1\.3초<\/time>/);
  assert.match(el('healthcheck-history').innerHTML,/2분 5초/);
  assert.equal(el('healthcheck-run').disabled,false);
});
test('running checks show elapsed time and prevent duplicate manual execution',async()=>{
  const el=await screen({id:'active',started_at:new Date(Date.now()-2500).toISOString(),duration_ms:0,status:'running',results:[],total:5,phase:'영상 연결'});
  assert.match(el('healthcheck-timing').innerHTML,/경과 시간/);
  assert.equal(el('healthcheck-progress').hidden,false);
  assert.equal(el('healthcheck-run').disabled,true);
});
test('external details are escaped and an empty history allows manual execution',async()=>{
  const el=await screen({id:'safe',started_at:new Date().toISOString(),duration_ms:12,status:'failed',results:[{group:'<script>',name:'<img>',status:'failed',detail:'<script>alert(1)</script>',duration_ms:12}]});
  assert(!el('healthcheck-results').innerHTML.includes('<script>'));
  assert.match(el('healthcheck-results').innerHTML,/&lt;script&gt;/);
  const empty=await screen(null);assert.equal(empty('healthcheck-run').disabled,false);
});
