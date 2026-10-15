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
   assert.equal(ctx.receiverLeft(anchor,width)+28,anchor.left+anchor.width/2);
 }
 assert.equal(ctx.receiverLeft({left:2000,width:100},390),318);
 assert.equal(ctx.receiverLeft({left:-20,width:20},390),16);
 assert.equal(ctx.receiverLeft({left:0,width:0},390),318);
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
 const toggle=app.slice(app.indexOf('function toggleScrap('),app.indexOf('function syncScrapUI'));
 assert.doesNotMatch(toggle,/deferUserAction/);
 assert.match(app,/else window.HScopeScrapMotion\?\.cancel\(key\)/);
 assert.match(app,/syncScrapUI\(key, true\)/);
 const html=fs.readFileSync('templates/index.html','utf8');assert(html.indexOf("filename='js/scrap-motion.js'")<html.indexOf("filename='js/app.js'"));
});
test('paper crumple deforms twelve faces into a smaller creased ball that bounces along a bounded floor and rebounds outside the right trash bin',async()=>{
 function element(){return {style:{setProperty(){}},children:[],classList:{add(){},remove(){}},setAttribute(){},removeAttribute(){},querySelectorAll:()=>[],cloneNode:()=>element(),appendChild(c){this.children.push(c)}};}
 const card=element();card.getBoundingClientRect=()=>({width:300,height:160});
 const animations=[];const window={addEventListener(){}};
 vm.runInNewContext(source,{window,document:{addEventListener(){},createElement:()=>element()},getComputedStyle:()=>Object.assign(['color'],{getPropertyValue:()=> '#fff'})});
 await window.HScopeScrapMotion.crumple(card,async(frames,options,node)=>animations.push({frames,options,node}));
 assert.equal(animations.length,15);assert.equal(card.children[0].children.length,15);
 assert(animations.every(a=>a.node!==card));
 assert.equal(animations[12].options.duration,1570);assert(animations.slice(0,12).every(a=>a.options.duration===760));
 const facets=animations.slice(0,12),ball=animations[12],bin=animations[13],impact=animations[14];
 assert.equal(new Set(facets.map(a=>a.frames[1].transform)).size,12);
 assert.match(ball.node.innerHTML,/viewBox="0 0 100 100"/);
 assert.match(ball.node.innerHTML,/stroke-linejoin="round"/);
 assert.equal(ball.frames[0].opacity,0);assert.equal(ball.frames[3].opacity,1);
 assert.match(ball.frames.at(-1).transform,/36px/);assert.equal(ball.frames.at(-1).opacity,0);
 assert.equal(ball.node.style.width,'40px');
 assert.equal(bin.node.className,'scrap-trash-bin');assert.equal(bin.node.style.left,'230px');assert.equal(bin.node.style.top,'68px');
 assert.match(bin.node.innerHTML,/scrap-trash-filled-paper/);assert.doesNotMatch(bin.node.innerHTML,/scrap-trash-lid/);assert.equal(bin.frames[2].opacity,1);
 assert.equal(ball.node.style.left,'24px');
 const impactIndex=ball.frames.findIndex(f=>f.transform.includes('scale(0.55,1.14)'));
 const x=frame=>Number(frame.transform.match(/translate\(([-.0-9]+)px/)[1]);
 assert(impactIndex>20);assert.equal(x(ball.frames[impactIndex]),x(ball.frames[impactIndex+1]));
 assert(x(ball.frames[impactIndex+2])<x(ball.frames[impactIndex]));
 assert(24+20+x(ball.frames[impactIndex])+40*.55/2<230+8);
 assert.match(bin.frames[4].transform,/rotate\(9deg\)/);
 assert.equal(impact.node.className,'scrap-bounce-impact');assert.equal(impact.frames[1].opacity,0);assert.equal(impact.frames[2].opacity,1);
 assert(impact.frames[1].offset<ball.frames[impactIndex].offset&&impact.frames[2].offset>ball.frames[impactIndex].offset);
 assert.match(impact.node.innerHTML,/<circle/);assert.equal(impact.frames.at(-1).opacity,0);
 assert(!card.children[0].children.some(node=>['scrap-bounce-ground','scrap-floor-pulse'].includes(node.className)));
 assert(facets.every(a=>a.node.style.clipPath.startsWith('polygon(')&&a.frames.at(-1).opacity===0));
});
for(const kind of ['card','lunch-card','finance-news-item'])for(const hidden of [false,true])test(`${kind}: genie uses ${hidden?'floating icon without revealing footer':'visible footer'} and cleans up its full card copy`,()=>{
 function element(){return {style:{setProperty(){}},children:[],isConnected:true,classList:{add(){},remove(){},contains:()=>false},setAttribute(){},removeAttribute(){},querySelectorAll:()=>[],getBoundingClientRect:()=>({left:316,top:540,width:44,height:44,bottom:584}),cloneNode:()=>element(),appendChild(c){this.children.push(c)},remove(){this.isConnected=false}};}
 const sourceCard=element();sourceCard.getBoundingClientRect=()=>({left:10,top:40,width:300,height:200,bottom:240});
 let footerWrites=0;const footer=element();footer.classList={add(){footerWrites++},remove(){footerWrites++}};
 const footerIcon=element();footerIcon.cloneNode=()=>Object.assign(element(),{fromFooterIcon:true});
 footer.querySelector=selector=>selector==='.fnav-ic svg'?footerIcon:{textContent:'스크랩'};
 footer.getBoundingClientRect=()=>({left:310,top:hidden?700:540,width:60,height:60,bottom:hidden?760:600});
 sourceCard.className=kind;
 const button={dataset:{key:'one'},parentElement:{closest(selector){assert.equal(selector,'[data-key]');return sourceCard;}},closest:()=>null};
 const body=element(),events={},frames=new Map(),timers=[];let id=0;body.classList.contains=()=>hidden;
 const window={innerWidth:390,innerHeight:650,matchMedia:()=>({matches:false}),addEventListener:(k,f)=>events[k]=f};
 const document={body,addEventListener:(k,f)=>events[k]=f,getElementById:()=>footer,createElement:()=>element()};
 vm.runInNewContext(source,{window,document,getComputedStyle:()=>Object.assign(['color'],{getPropertyValue:()=> '#fff'}),requestAnimationFrame:fn=>{frames.set(++id,fn);return id},cancelAnimationFrame:()=>{},setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length},clearTimeout(){}});
 const run=t=>{const fn=frames.get(id);fn(t)};
 window.HScopeScrapMotion.save(button);assert.equal(body.children.length,hidden?2:1);const layer=body.children.at(-1);assert.equal(layer.children.length,32);
 if(hidden){assert.equal(body.children[0].style.left,'312px');assert.equal(body.children[0].style.right,'auto');assert.equal(body.children[0].children[0].fromFooterIcon,true);assert.equal(body.children[0].children[1].textContent,'스크랩');}
 assert.equal(layer.children[0].style.width,'300px'); // full card, never the 36px bookmark button
 run(0);run(260);run(520);assert.equal(layer.isConnected,false);assert.equal(sourceCard.isConnected,true);assert.equal(sourceCard.style.transform,undefined);
 if(hidden){assert.equal(body.children[0].isConnected,true);assert.equal(timers.at(-1).ms,320);timers.at(-1).fn();assert.equal(body.children[0].isConnected,false);}
 window.HScopeScrapMotion.save(button);const last=body.children.at(-1);window.HScopeScrapMotion.cancel('one');assert.equal(last.isConnected,false);assert.equal(sourceCard.isConnected,true);
 window.HScopeScrapMotion.save(button);document.hidden=true;events.visibilitychange();assert(body.children.every(c=>!c.isConnected));
 assert.equal(footerWrites,hidden?0:2); // visible receiver pop only; hidden footer is never mutated
});

test('desktop and mobile crumple layouts stay centered, visible, and within a 420px stage',()=>{
 const ctx=vm.createContext({});vm.runInContext(geometry,ctx);
 for(const width of [184,320,768,1440,2560]){
   const rect={left:20,top:160,width:width-40,height:80},g=ctx.crumpleGeometry(rect,{width,height:900});
   assert(g.hitX<=296);assert(g.ballLeft>=0);assert(g.binLeft+54<=rect.width);assert(g.size>=23&&g.size<=40);
   if(width>=768) assert.equal(g.hitX,296);
   assert.equal(20+g.binLeft+70-(Math.min(420,rect.width))/2,width/2);
 }
 for(const rect of [{left:20,top:-300,width:1000,height:800},{left:20,top:600,width:1000,height:400}]){
   const g=ctx.crumpleGeometry(rect,{width:1200,height:800});
   assert(rect.top+g.centerY>=80&&rect.top+g.centerY<=680);
 }
});
test('floor hops keep the same travel speed as distance grows and touch the ground repeatedly',()=>{
 const ctx=vm.createContext({});vm.runInContext(geometry,ctx);let previous=0;
 for(const width of [200,300,420,1440]){
   const g=ctx.crumpleGeometry({left:0,top:100,width,height:160},{width,height:800}),p=ctx.floorBouncePlan(g);
   assert(p.travel>=previous);previous=p.travel;assert(g.hitX/p.travel*1000<=220.0001);
   assert(p.hops>=2);assert.equal(p.floorHits.length,p.hops);
   const travel=p.samples.filter(s=>s.time>=420&&s.time<=p.hitTime);
   assert.equal(travel.filter(s=>Math.abs(s.y+s.sy*g.size/2-54)<.001).length,p.hops+1);
   for(const hit of p.floorHits){assert(p.samples.some(s=>s.time===hit.time&&Math.abs(s.y+s.sy*g.size/2-54)<.001&&s.sy<1));}
   for(let i=1;i<travel.length;i++){
     const speed=(travel[i].x-travel[i-1].x)/(travel[i].time-travel[i-1].time)*1000;assert(speed<=220.0001);
   }
 }
});
