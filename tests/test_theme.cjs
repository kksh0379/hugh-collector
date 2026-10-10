const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/theme.js','utf8');
function setup(stored={},blocked=false){
 const values=new Map(Object.entries(stored)),ready={},events={};
 const buttons=[0,1].map(()=>({attrs:{},addEventListener(k,f){this[k]=f;},setAttribute(k,v){this.attrs[k]=v;}}));
 const reader={dark:false,classList:{toggle(k,v){reader.dark=v;}}};
 const root={dataset:{},style:{}},meta={};
 const ctx={document:{documentElement:root,querySelector:()=>meta,getElementById:()=>reader,querySelectorAll:()=>buttons,addEventListener:(k,f)=>ready[k]=f},window:{addEventListener:(k,f)=>events[k]=f},localStorage:{getItem(k){if(blocked)throw Error('denied');return values.get(k)||null;},setItem(k,v){if(blocked)throw Error('denied');values.set(k,v);}}};
 vm.runInNewContext(source,ctx);return {ctx,values,ready,events,buttons,reader,root,meta};
}
test('saved theme applies before DOM ready and both controls share state',()=>{
 const s=setup({hscopeTheme:'black'});assert.equal(s.root.dataset.theme,'black');assert.equal(s.meta.content,'#000000');s.ready.DOMContentLoaded();
 assert.equal(s.reader.dark,true);assert.equal(s.buttons[0].attrs['aria-pressed'],'true');s.buttons[1].click();
 assert.equal(s.root.dataset.theme,'light');assert.equal(s.reader.dark,false);assert.equal(s.buttons[0].attrs['aria-pressed'],'false');assert.equal(s.values.get('hscopeTheme'),'light');
 s.buttons[0].click();assert.equal(s.reader.dark,true);assert.equal(s.buttons[1].attrs['aria-pressed'],'true');
});
test('theme works when storage is denied and old reader preference migrates without overriding explicit light',()=>{
 const s=setup({},true);s.ready.DOMContentLoaded();assert.doesNotThrow(()=>s.buttons[0].click());assert.equal(s.root.dataset.theme,'black');
 assert.equal(setup({readerDark:'1'}).root.dataset.theme,'black');assert.equal(setup({readerDark:'1',hscopeTheme:'light'}).root.dataset.theme,'light');
});
test('other tab preference changes and clearing storage synchronize without writing back',()=>{
 const s=setup({hscopeTheme:'light'});s.ready.DOMContentLoaded();s.events.storage({key:'hscopeTheme',newValue:'black'});assert.equal(s.reader.dark,true);assert.equal(s.values.get('hscopeTheme'),'light');
 s.events.storage({key:null,newValue:null});assert.equal(s.reader.dark,false);
});
test('header donation preserves safe link fallback and isolates popup opener',()=>{
 const header={href:'https://aq.gy/f/C4DRg',addEventListener(k,f){this[k]=f;}};const popup={opener:{}};
 const window={open:()=>popup};const document={getElementById:()=>header};vm.runInNewContext(fs.readFileSync('static/js/credit-help.js','utf8'),{window,document});
 let prevented=false;const event={preventDefault(){prevented=true;}};header.click(event);assert.equal(prevented,true);assert.equal(popup.opener,null);
 for(const open of [()=>null,()=>{throw Error('blocked');}]){prevented=false;window.open=open;header.click(event);assert.equal(prevented,false);}
});
