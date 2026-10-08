const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const src=fs.readFileSync('static/js/app.js','utf8');
test('successful authentication closes login and notifies without awaiting personal data',async()=>{
 let handler,resolve;const pending=new Promise(r=>resolve=r),button={textContent:'로그인',disabled:false},modal={hidden:false},notices=[];
 const ctx=vm.createContext({document:{getElementById:id=>id==='login-form'?{addEventListener:(name,fn)=>handler=fn}:id==='login-submit'?button:{replaceChildren(){}}},loginErr:{},loginModal:modal,loginRequestBody:()=>({role:'user'}),fetch:async()=>({json:async()=>({ok:true,user:'alice',display_name:'앨리스'})}),applyAuthUI(){ctx.CURRENT_USER='alice';},loadMyData:()=>pending,applyUserStateToDom(){},updateScrapBadge(){},CURRENT_USER:null,AUTH_GENERATION:1,pendingScrapKey:null,toast:m=>notices.push(m)});
 vm.runInContext(src.slice(src.indexOf('let loginSubmitting ='),src.indexOf('document.getElementById("logout-btn")')),ctx);
 await handler({preventDefault(){}});assert.equal(modal.hidden,true);assert.match(notices[0],/로그인했어요/);assert.equal(button.disabled,false);resolve(true);
});
function setup(){let calls=0,resolve,reject;const pending=new Promise((r,j)=>{resolve=r;reject=j;});const ctx=vm.createContext({CURRENT_USER:'alice',AUTH_GENERATION:1,READ:new Set(['old']),SCRAP:{},GROUPS:[],fetchData:()=>{calls++;return pending;},document:{getElementById:()=>null},applyUserStateToDom(){},updateScrapBadge(){},toast(){}});vm.runInContext(src.slice(src.indexOf('let MY_DATA_REQUEST ='),src.indexOf('// 이미 렌더된 카드')),ctx);return {ctx,resolve,reject,calls:()=>calls};}
test('personal reads coalesce and cannot restore data after logout',async()=>{
 const {ctx,resolve,calls}=setup();const one=ctx.loadMyData(),two=ctx.loadMyData();assert.equal(calls(),1);ctx.CURRENT_USER=null;ctx.AUTH_GENERATION++;
 resolve({json:async()=>({reads:['private'],scraps:[{key:'private'}],groups:[]})});assert.equal(await one,false);assert.equal(await two,false);assert.equal(ctx.READ.has('private'),false);assert.equal(ctx.SCRAP.private,undefined);
});
test('a queued change runs after data arrives, and failure does not run a change',async()=>{
 for(const fail of [false,true]){const {ctx,resolve,reject}=setup();let executed=0;assert.equal(ctx.deferUserAction(()=>executed++),true);assert.equal(executed,0);if(fail)reject(Error('offline'));else resolve({json:async()=>({reads:[],scraps:[],groups:[]})});await vm.runInContext('MY_DATA_REQUEST.promise',ctx);await Promise.resolve();assert.equal(executed,fail?0:1);}
});
