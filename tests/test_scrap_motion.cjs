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
test('genie copy preserves the source, completes at the footer, and cleans up on cancellation',()=>{
 function element(){return {style:{setProperty(){}},children:[],isConnected:true,classList:{add(){},remove(){}},setAttribute(){},removeAttribute(){},querySelectorAll:()=>[],cloneNode:()=>element(),appendChild(c){this.children.push(c)},remove(){this.isConnected=false}};}
 const sourceCard=element();sourceCard.getBoundingClientRect=()=>({left:10,top:40,width:300,height:200,bottom:240});
 const anchorClasses=new Set(),footerBar=element();footerBar.classList={add:k=>anchorClasses.add(k),remove:k=>anchorClasses.delete(k)};
 const footer=element();footer.closest=()=>footerBar;footer.getBoundingClientRect=()=>({left:310,top:anchorClasses.has('scrap-motion-anchor')?540:700,width:60,height:60,bottom:anchorClasses.has('scrap-motion-anchor')?600:760});
 const button={dataset:{key:'one'},closest:()=>sourceCard};
 const body=element(),events={},frames=new Map();let id=0;
 const window={innerHeight:650,matchMedia:()=>({matches:false}),addEventListener:(k,f)=>events[k]=f};
 const document={body,addEventListener:(k,f)=>events[k]=f,getElementById:()=>footer,createElement:()=>element()};
 vm.runInNewContext(source,{window,document,getComputedStyle:()=>Object.assign(['color'],{getPropertyValue:()=> '#fff'}),requestAnimationFrame:fn=>{frames.set(++id,fn);return id},cancelAnimationFrame:()=>{},setTimeout:()=>1,clearTimeout(){}});
 const run=t=>{const fn=frames.get(id);fn(t)};
 window.HScopeScrapMotion.save(button);assert.equal(body.children.length,1);assert.equal(body.children[0].children.length,32);
 assert(anchorClasses.has('scrap-motion-anchor'));
 run(0);run(260);run(520);assert.equal(body.children[0].isConnected,false);assert.equal(sourceCard.isConnected,true);assert.equal(sourceCard.style.transform,undefined);assert.equal(anchorClasses.size,0);
 window.HScopeScrapMotion.save(button);const layer=body.children[1];window.HScopeScrapMotion.cancel('one');assert.equal(layer.isConnected,false);assert.equal(sourceCard.isConnected,true);assert.equal(anchorClasses.size,0);
 window.HScopeScrapMotion.save(button);document.hidden=true;events.visibilitychange();assert.equal(body.children[2].isConnected,false);
});
