const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const apply=source.slice(source.indexOf('function applyViewClasses('),source.indexOf('function setView('));
const viewCode=source.slice(source.indexOf('function setScrapView('),source.indexOf('updateScrapBadge();',source.indexOf('function setScrapView(')));
const preference=source.slice(source.indexOf('let scrapViewMode ='),source.indexOf('// 게시글 고유키:',source.indexOf('let scrapViewMode =')));
function setup(saved,blocked=false){
 const storage=new Map([['nvView','list']]);if(saved)storage.set('scrapView',saved);
 function classes(){const set=new Set();return {set,toggle(k,on){on?set.add(k):set.delete(k)}};}
 const body={classList:classes()},view={hidden:false,classList:classes()};
 const buttons=['list','album'].map(mode=>({dataset:{scrapView:mode},classList:classes(),attrs:{},setAttribute(k,v){this.attrs[k]=v}}));
 let renders=0;
 const ctx={document:{body,getElementById:id=>id==='view-scrap'?view:null,querySelectorAll:()=>buttons},localStorage:{getItem:k=>{if(blocked)throw Error();return storage.get(k)},setItem:(k,v)=>{if(blocked)throw Error();storage.set(k,v)}},scrapFilterGroup:'group-one',scrapQuery:'query',renderScraps:()=>renders++};
 vm.createContext(ctx);vm.runInContext(preference+apply+viewCode,ctx);
 return {ctx,body,view,buttons,storage,renders:()=>renders,mode:()=>vm.runInContext('scrapViewMode',ctx)};
}
test('scrap view is independent of the news preference and button state matches the selected mode',()=>{
 const s=setup();s.ctx.onShowScrap();assert.equal(s.mode(),'album');assert(s.view.classList.set.has('scrap-album'));assert(s.body.classList.set.has('view-card'));assert.equal(s.buttons[1].attrs['aria-pressed'],'true');
 s.ctx.setScrapView('list');assert(s.body.classList.set.has('view-list'));assert(!s.view.classList.set.has('scrap-album'));assert.equal(s.buttons[0].attrs['aria-pressed'],'true');assert.equal(s.storage.get('nvView'),'list');assert.equal(s.storage.get('scrapView'),'list');
 s.ctx.applyViewClasses('card');assert(s.body.classList.set.has('view-list')); // background news updates cannot override scraps
 s.view.hidden=true;s.ctx.applyViewClasses('card');assert(s.body.classList.set.has('view-card'));
});
test('saved scrap preference survives reopening and toggles do not redraw cards or pending animations',()=>{
 const s=setup('list');s.ctx.onShowScrap();assert.equal(s.mode(),'list');assert.equal(s.renders(),1);
 s.ctx.setScrapView('album');s.ctx.setScrapView('list');assert.equal(s.renders(),1);s.ctx.onShowScrap();assert.equal(s.mode(),'list');
 const reloaded=setup(s.storage.get('scrapView'));reloaded.ctx.onShowScrap();assert(reloaded.body.classList.set.has('view-list'));
});
test('invalid or unavailable storage uses album view without preventing switching',()=>{
 for(const s of [setup('wrong'),setup(null,true)]){s.ctx.onShowScrap();assert.equal(s.mode(),'album');assert.doesNotThrow(()=>s.ctx.setScrapView('list'));assert.equal(s.mode(),'list');}
});
