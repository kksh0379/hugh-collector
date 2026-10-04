const {test}=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
function setup(extra={}){
 const nodes={};for(const id of ['msg-biz','msg-boards','msg-social','msg-cat','collect-biz','collect-boards','collect-social','purge-db-btn','list-biz'])nodes[id]={style:{},innerHTML:'existing',textContent:'',disabled:false};
 nodes['biz-reset-scope']={value:'biz-all'};
 const checks=['all','동향','게시판','영상'].map(cat=>({dataset:{cat},checked:false})),polls=[];
 const ctx=vm.createContext({document:{getElementById:id=>nodes[id],querySelector:()=>({dataset:{tab:'biz'}}),querySelectorAll:()=>checks},bizSrc:new Set(['news']),catRunInline:s=>s,catSpin:s=>s,uiIcon:()=>'',_startPolling:g=>polls.push(g),fetch:async()=>({ok:true,json:async()=>({ok:true,staged:true,recollect_started:['biz','boards','social']})}),...extra});
 vm.runInContext(source.slice(source.indexOf('function revealCollectedBizSource'),source.indexOf('// 페이지 로드/복귀')),ctx);
 vm.runInContext(source.slice(source.indexOf('const TAB_KO'),source.indexOf('document.getElementById("purge-db-btn").addEventListener')),ctx);
 return {ctx,nodes,checks,polls};
}
test('polling starts only after accepted start response',async()=>{
 let release;const pending=new Promise(r=>release=r),c=setup({fetch:()=>pending});
 const running=c.ctx.runCrawl(c.nodes['collect-biz'],'biz',c.nodes['msg-biz']);assert.equal(c.polls.length,0);
 release({ok:true,json:async()=>({running:true})});await running;assert.deepEqual(c.polls,['biz']);
});
test('rejected start unlocks button and does not poll',async()=>{
 const c=setup({fetch:async()=>({ok:false,json:async()=>({error:'unauthorized'})})});
 await c.ctx.runCrawl(c.nodes['collect-biz'],'biz',c.nodes['msg-biz']);assert.equal(c.nodes['collect-biz'].disabled,false);assert.equal(c.polls.length,0);assert.match(c.nodes['msg-biz'].textContent,/실패/);
});
test('merged reset preserves visible list and polls all selected sources',async()=>{
 let body;const c=setup({fetch:async(u,o)=>{body=JSON.parse(o.body);return {ok:true,json:async()=>({ok:true,staged:true,recollect_started:['biz','boards','social']})}}});
 await c.ctx.purgeDb();assert.equal(body.scope,'biz-all');assert.equal(c.nodes['list-biz'].innerHTML,'existing');assert.deepEqual(c.polls,['biz','boards','social']);c.nodes['biz-reset-scope'].value='boards';assert.equal(c.ctx.purgeScope(),'boards');
});
test('collected hidden source becomes visible without enabling others',()=>{
 const c=setup();c.ctx.revealCollectedBizSource('social');assert.equal(c.ctx.bizSrc.has('video'),true);assert.equal(c.checks.find(c=>c.dataset.cat==='영상').checked,true);assert.equal(c.checks.find(c=>c.dataset.cat==='게시판').checked,false);
});
test('source progress remains independent and partial result is a warning',()=>{
 const c=setup({loadCat:()=>{},loadGame:()=>{},loadNews:()=>{},loadBiz:()=>{},loadSecurity:()=>{},loadEvent:()=>{}});
 vm.runInContext(source.slice(source.indexOf('const CRAWL_UI'),source.indexOf('async function _pollCrawl')),c.ctx);
 c.ctx._renderCrawlState('boards',{running:true,progress:'board progress'});c.ctx._renderCrawlState('social',{running:true,progress:'video progress'});
 assert.equal(c.nodes['msg-boards'].innerHTML,'board progress');assert.equal(c.nodes['msg-social'].innerHTML,'video progress');c.ctx._renderCrawlState('biz',{result:{warning:'preserved',new:1}});assert.match(c.nodes['msg-biz'].textContent,/일부 수집/);
});
