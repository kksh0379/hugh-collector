const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/app.js', 'utf8');
const code = source.slice(source.indexOf('async function refreshCurrentPage()'));
const listeners = {}, calls = [];
let view = 'collector', tab = 'news', modal = false;
const hint = {setAttribute(){}, style:{}};
const target = {closest(){return null;}, parentElement:null, scrollHeight:0, clientHeight:0};
const context = {document:{
  body:{appendChild(){}}, documentElement:{},
  createElement:()=>hint,
  querySelector(selector){return selector === '.fnav.active' ? {dataset:{nav:view}} : modal ? {} : null;},
  getElementById:()=>({value:'saved-report'}),
  addEventListener:(type,fn)=>listeners[type]=fn,
},window:{scrollY:0},getComputedStyle:()=>({overflowY:'visible'}),
activeTab:()=>tab,toast:msg=>calls.push(msg),renderScraps:()=>calls.push('renderScraps'),
loadMyData:async()=>calls.push('mydata'),loadReport:async id=>calls.push(id)};
for(const name of ['Cat','Game','News','Biz','Security','Event','Boards','Social']) context['load'+name]=async()=>calls.push(name);
for(const name of ['Finance','Videos','Lunch']) context.window['refresh'+name]=async()=>calls.push(name);
vm.createContext(context);vm.runInContext(code,context);
const start=()=>listeners.touchstart({target,touches:[{clientX:0,clientY:0}]});
const move=(x,y)=>{let prevented=false;listeners.touchmove({touches:[{clientX:x,clientY:y}],cancelable:true,preventDefault(){prevented=true;}});return prevented;};
(async()=>{
  start();move(0,40);await listeners.touchend();assert.deepEqual(calls,[]);
  start();assert.equal(move(0,90),true);await listeners.touchend();assert.deepEqual(calls,['News']);
  view='finance';start();move(0,90);await listeners.touchend();assert.equal(calls.at(-1),'Finance');
  view='report';start();move(0,90);await listeners.touchend();assert.equal(calls.at(-1),'saved-report');
  const before=calls.length;
  start();move(90,10);await listeners.touchend();assert.equal(calls.length,before);
  modal=true;start();move(0,90);await listeners.touchend();assert.equal(calls.length,before);modal=false;
  context.window.scrollY=100;start();move(0,90);await listeners.touchend();assert.equal(calls.length,before);context.window.scrollY=0;
  target.scrollHeight=500;target.clientHeight=100;context.getComputedStyle=()=>({overflowY:'auto'});
  start();move(0,90);await listeners.touchend();assert.equal(calls.length,before);
  assert.equal(hint.hidden,true);
  console.log('Pull refresh routing, threshold, modal, horizontal gesture and inner scroll checks passed');
})();
