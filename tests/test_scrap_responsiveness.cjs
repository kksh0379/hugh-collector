const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const src=fs.readFileSync('static/js/app.js','utf8');
const personal=src.slice(src.indexOf('let MY_DATA_REQUEST ='),src.indexOf('// 이미 렌더된 카드'));
const toggle=src.slice(src.indexOf('function toggleScrap('),src.indexOf('function syncScrapUI'));
const restore=src.slice(src.indexOf('function restoreScrap('),src.indexOf('function toggleScrap('));
const tick=()=>new Promise(setImmediate);
function setup(cache){
 let resolveRead,rejectRead;const reading=new Promise((r,j)=>{resolveRead=r;rejectRead=j});
 const calls=[],motions=[],messages=[],storage=new Map(cache||[]);
 const ctx={CURRENT_USER:'alice',AUTH_GENERATION:1,READ:new Set(),SCRAP:{},GROUPS:[],ITEM_INDEX:{a:{key:'a',title:'Article'}},SCRAP_REMOVALS:new Map(),
   fetchData:()=>reading,api:(path,body)=>new Promise((resolve,reject)=>calls.push({path,body,resolve,reject})),
   document:{getElementById:()=>null},sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
   isLoggedIn:()=>!!ctx.CURRENT_USER,isScrapped:k=>!!ctx.SCRAP[k],syncScrapUI(){},applyUserStateToDom(){},updateScrapBadge(){},
   toast:m=>messages.push(m),openLogin(){},flyToScrap:()=>motions.push('save'),window:{HScopeScrapMotion:{unsave:()=>motions.push('unsave')}},Date};
 vm.createContext(ctx);vm.runInContext(personal+restore+toggle,ctx);return {ctx,calls,motions,messages,storage,resolveRead,rejectRead};
}
const button={closest:()=>null};
test('a tap animates and writes immediately while initial personal data is still pending',async()=>{
 const s=setup();const loading=s.ctx.loadMyData();s.ctx.toggleScrap('a',button);
 assert.equal(s.ctx.SCRAP.a.title,'Article');assert.deepEqual(s.motions,['save']);
 await tick();assert.equal(s.calls.length,1);assert.equal(s.calls[0].body.op,'add');
 s.resolveRead({json:async()=>({scraps:[],reads:[],groups:[]})});await loading;assert(s.ctx.SCRAP.a);
 s.calls[0].resolve({ok:true,item:{key:'a',title:'Article',groups:['existing']}});await tick();assert.deepEqual(s.ctx.SCRAP.a.groups,['existing']);
});
test('late initial data cannot resurrect an item cancelled during loading',async()=>{
 const s=setup();s.ctx.SCRAP.a={key:'a'};const loading=s.ctx.loadMyData();s.ctx.toggleScrap('a',button);
 assert.equal(s.ctx.SCRAP.a,undefined);assert.deepEqual(s.motions,['unsave']);await tick();
 s.resolveRead({json:async()=>({scraps:[{key:'a'}],reads:[],groups:[]})});await loading;assert.equal(s.ctx.SCRAP.a,undefined);
 s.calls[0].resolve({ok:true});await tick();
});
test('rapid add then delete serializes writes without blocking either visual response',async()=>{
 const s=setup();s.ctx.toggleScrap('a',button);s.ctx.toggleScrap('a',button);await tick();
 assert.deepEqual(s.motions,['save','unsave']);assert.equal(s.calls.length,1);assert.equal(s.ctx.SCRAP.a,undefined);
 s.calls[0].resolve({ok:true,item:{key:'a'}});await tick();assert.equal(s.calls.length,2);assert.equal(s.calls[1].body.op,'del');assert.equal(s.ctx.SCRAP.a,undefined);
 s.calls[1].resolve({ok:true});await tick();
});
test('failed sequential operations restore confirmed server state, not an unsaved intermediate state',async()=>{
 const s=setup();s.ctx.toggleScrap('a',button);s.ctx.toggleScrap('a',button);await tick();
 s.calls[0].reject(Error('offline'));await tick();s.calls[1].reject(Error('offline'));await tick();assert.equal(s.ctx.SCRAP.a,undefined);assert.equal(s.messages.filter(m=>m.includes('저장하지 못')).length,1);
});
test('an old user response cannot modify another account',async()=>{
 const s=setup();s.ctx.toggleScrap('a',button);await tick();s.ctx.CURRENT_USER='bob';s.ctx.AUTH_GENERATION=2;s.ctx.SCRAP={b:{key:'b'}};
 s.calls[0].reject(Error('offline'));await tick();assert.equal(s.ctx.SCRAP.a,undefined);assert(s.ctx.SCRAP.b);assert(!s.messages.some(m=>m.includes('저장하지 못')));
});
test('same-user session cache displays immediately and survives a failed refresh',async()=>{
 const cached=JSON.stringify({user:'alice',ts:Date.now(),scraps:[{key:'a',title:'Cached'}],reads:['r'],groups:[]});
 const s=setup([['hscopePersonal:alice',cached]]);const loading=s.ctx.loadMyData();assert.equal(s.ctx.SCRAP.a.title,'Cached');assert(s.ctx.READ.has('r'));
 s.rejectRead(Error('offline'));await loading;assert.equal(s.ctx.SCRAP.a.title,'Cached');
});
test('undo during an in-flight delete restores original order and groups, then persists after deletion',async()=>{
 const s=setup();let undo;s.ctx.window.HScopeScrapUndo={show:r=>undo=r,clear(){}};
 s.ctx.SCRAP.a={key:'a',title:'Original',ts:123,groups:['one']};s.ctx.toggleScrap('a',{closest:()=>true});await tick();
 assert.equal(s.calls[0].body.op,'del');s.ctx.restoreScrap(undo);assert.equal(s.ctx.SCRAP.a.ts,123);assert.deepEqual([...s.ctx.SCRAP.a.groups],['one']);
 s.calls[0].resolve({ok:true});await tick();assert.equal(s.calls[1].body.op,'restore');assert.equal(s.calls[1].body.item.ts,123);s.calls[1].resolve({ok:true,item:s.calls[1].body.item});await tick();assert.equal(s.ctx.SCRAP.a.title,'Original');
});
test('undo from an old account or generation cannot restore or send a request',async()=>{
 const s=setup();s.ctx.restoreScrap({key:'a',user:'bob',generation:1,snapshot:{key:'a',ts:100}});s.ctx.restoreScrap({key:'a',user:'alice',generation:0,snapshot:{key:'a',ts:100}});await tick();assert.equal(s.calls.length,0);assert.equal(s.ctx.SCRAP.a,undefined);
});
