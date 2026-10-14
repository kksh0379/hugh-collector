const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('static/js/scrap-motion.js','utf8');
const geometry=source.slice(source.indexOf('  function smooth'),source.indexOf('  function cancel'));
test('genie starts at card geometry, narrows bottom first, and ends at the target',()=>{
 const ctx=vm.createContext({});vm.runInContext(geometry,ctx);
 const rect={left:24,top:220,width:432,height:250,bottom:470},target={x:440,y:757};
 const top=ctx.stripGeometry(rect,target,0,0,1/32),bottom=ctx.stripGeometry(rect,target,0,1,1/32);
 assert.equal(top.x,24);assert.equal(top.y,220);assert.equal(top.sx,1);assert.equal(bottom.y,470);
 const earlyTop=ctx.stripGeometry(rect,target,.35,0,1/32),earlyBottom=ctx.stripGeometry(rect,target,.35,1,1/32);
 assert(earlyTop.sx>earlyBottom.sx);assert(earlyBottom.y>rect.bottom);
 for(const v of [0,.5,1]){const end=ctx.stripGeometry(rect,target,1,v,1/32);assert.equal(end.y,757);assert.equal(end.x,437.5);assert(end.sy>0);}
 for(let t=0;t<=1;t+=.05)for(let v=0;v<=1;v+=.1){const g=ctx.stripGeometry(rect,target,t,v,1/32);assert(Object.values(g).every(Number.isFinite));assert(g.sx>0&&g.sy>0);}
});
test('floating receiver follows the actual responsive tab center at mobile, tablet and desktop widths',()=>{
 const ctx=vm.createContext({});vm.runInContext(geometry,ctx);
 for(const [width,anchor] of [[390,{left:312,width:60}],[768,{left:650,width:98}],[1440,{left:990,width:110}]]){
   assert.equal(ctx.receiverLeft(anchor,width)+22,anchor.left+anchor.width/2);
 }
 assert.equal(ctx.receiverLeft({left:2000,width:100},390),330);
 assert.equal(ctx.receiverLeft({left:-20,width:20},390),16);
 assert.equal(ctx.receiverLeft({left:0,width:0},390),330);
});
test('ordinary unsave touches only the icon; reduced motion skips it',()=>{
 for(const reduced of [false,true]){
  const classes=new Set(),events={},timers=[];const window={matchMedia:()=>({matches:reduced}),addEventListener(){}};
  const document={addEventListener:(k,f)=>events[k]=f};
  vm.runInNewContext(source,{window,document,cancelAnimationFrame(){},clearTimeout(){},setTimeout:(fn,ms)=>timers.push({fn,ms})});
  const button={dataset:{key:'one'},classList:{add:k=>classes.add(k),remove:k=>classes.delete(k)}};
  window.HScopeScrapMotion.unsave(button);assert.equal(classes.has('scrap-unsaving'),!reduced);
  if(!reduced){assert.equal(timers[0].ms,280);timers[0].fn();assert.equal(classes.size,0);}
 }
});
test('save skips DOM work when reduced motion is requested; cancellation is safe',()=>{
 const window={matchMedia:()=>({matches:true}),addEventListener(){}};
 vm.runInNewContext(source,{window,document:{addEventListener(){}}});
 assert.doesNotThrow(()=>window.HScopeScrapMotion.save({dataset:{key:'one'}}));
 assert.doesNotThrow(()=>window.HScopeScrapMotion.cancel('missing'));
});
test('click integration keeps scrap-menu exits separate and rolls back failed save effects',()=>{
 const app=fs.readFileSync('static/js/app.js','utf8');
 assert.match(app,/!fromEl.closest\('#scrap-list'\)/);
 assert.match(app,/deferUserAction\(\(\) => toggleScrap\(key, fromEl\)\)/);
 assert.match(app,/else window.HScopeScrapMotion\?\.cancel\(key\)/);
 assert.match(app,/syncScrapUI\(key, true\)/);
 const html=fs.readFileSync('templates/index.html','utf8');assert(html.indexOf("filename='js/scrap-motion.js'")<html.indexOf("filename='js/app.js'"));
});
for(const kind of ['card','lunch-card','finance-news-item'])for(const hidden of [false,true])test(`${kind}: genie uses ${hidden?'floating icon without revealing footer':'visible footer'} and cleans up its full card copy`,()=>{
 function element(){return {style:{setProperty(){}},children:[],isConnected:true,classList:{add(){},remove(){},contains:()=>false},setAttribute(){},removeAttribute(){},querySelectorAll:()=>[],getBoundingClientRect:()=>({left:316,top:540,width:44,height:44,bottom:584}),cloneNode:()=>element(),appendChild(c){this.children.push(c)},remove(){this.isConnected=false}};}
 const sourceCard=element();sourceCard.getBoundingClientRect=()=>({left:10,top:40,width:300,height:200,bottom:240});
 let footerWrites=0;const footer=element();footer.classList={add(){footerWrites++},remove(){footerWrites++}};
 footer.getBoundingClientRect=()=>({left:310,top:hidden?700:540,width:60,height:60,bottom:hidden?760:600});
 sourceCard.className=kind;
 const button={dataset:{key:'one'},parentElement:{closest(selector){assert.equal(selector,'[data-key]');return sourceCard;}},closest:()=>null};
 const body=element(),events={},frames=new Map(),timers=[];let id=0;body.classList.contains=()=>hidden;
 const window={innerWidth:390,innerHeight:650,matchMedia:()=>({matches:false}),addEventListener:(k,f)=>events[k]=f};
 const document={body,addEventListener:(k,f)=>events[k]=f,getElementById:()=>footer,createElement:()=>element()};
 vm.runInNewContext(source,{window,document,getComputedStyle:()=>Object.assign(['color'],{getPropertyValue:()=> '#fff'}),requestAnimationFrame:fn=>{frames.set(++id,fn);return id},cancelAnimationFrame:()=>{},setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length},clearTimeout(){}});
 const run=t=>{const fn=frames.get(id);fn(t)};
 window.HScopeScrapMotion.save(button);assert.equal(body.children.length,hidden?2:1);const layer=body.children.at(-1);assert.equal(layer.children.length,32);
 if(hidden){assert.equal(body.children[0].style.left,'318px');assert.equal(body.children[0].style.right,'auto');}
 assert.equal(layer.children[0].style.width,'300px'); // full card, never the 36px bookmark button
 run(0);run(260);run(520);assert.equal(layer.isConnected,false);assert.equal(sourceCard.isConnected,true);assert.equal(sourceCard.style.transform,undefined);
 if(hidden){assert.equal(body.children[0].isConnected,true);assert.equal(timers.at(-1).ms,320);timers.at(-1).fn();assert.equal(body.children[0].isConnected,false);}
 window.HScopeScrapMotion.save(button);const last=body.children.at(-1);window.HScopeScrapMotion.cancel('one');assert.equal(last.isConnected,false);assert.equal(sourceCard.isConnected,true);
 window.HScopeScrapMotion.save(button);document.hidden=true;events.visibilitychange();assert(body.children.every(c=>!c.isConnected));
 assert.equal(footerWrites,hidden?0:2); // visible receiver pop only; hidden footer is never mutated
});
