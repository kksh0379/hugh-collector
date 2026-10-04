const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/videos.js','utf8');
const flush=()=>new Promise(setImmediate);
function setup() {
 const elements=new Map(), stored=new Map([['hscope-video-library-v1',JSON.stringify([{id:'123',series:1,episode:8,title:'작품 A'}])]]), listeners={};
 function element(tag='div') { return {tag,children:[],dataset:{},attrs:{},value:'',textContent:'',hidden:false,setAttribute(k,v){this.attrs[k]=v},append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=nodes},querySelectorAll(){return this.children.filter(x=>x.tag==='button')},querySelector(tag){return this.children.find(x=>x.tag===tag)||null},remove(){}}; }
 const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
 el('videos-detail').hidden=true;el('videos-detail-body').hidden=true;
 const location={href:'https://hscope.onrender.com/'}, entries=[{url:location.href,state:null}];let position=0;
 const win={scrollY:900,scrollTo(x,y){this.scrollY=typeof x==='object'?x.top:y},addEventListener(name,fn){listeners[name]=fn}};
 const history={state:null,pushState(state,unused,url){entries.splice(++position);entries.push({state,url:String(url)});this.state=state;location.href=String(url)},replaceState(state,unused,url){entries[position]={state,url:String(url)};this.state=state;location.href=String(url)},back(){if(position){const entry=entries[--position];this.state=entry.state;location.href=entry.url;listeners.popstate()}}};
 const works=[{id:'123',series:1,episode:1,title:'작품 A'},{id:'456',series:1,episode:1,title:'작품 B'}];
 const c=vm.createContext({URL,AbortController,location,history,window:win,document:{getElementById:el,createElement:element},localStorage:{getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v)},setTimeout:()=>1,clearTimeout(){},fetch:async url=>({ok:true,json:async()=>url.includes('/library')?{items:works}:{id:'123',title:'작품 A',series:[{id:1,episodes:[1,8]}]}})});
 vm.runInContext(source,c);
 return {el,win,history,location,stored,async start(){win.onShowVideos();await flush()},favoriteCount(){return JSON.parse(stored.get('hscope-video-favorites-v2')||'[]').length}};
}
test('old automatic viewing history is not treated as favorites; opening details does not save',async()=>{
 const s=setup();await s.start();s.el('videos-saved').onclick();assert.match(s.el('videos-count').textContent,/총 0개/);
 s.el('videos-all').onclick();await s.el('videos-library').children[0].children[0].onclick();
 assert.equal(s.favoriteCount(),0);assert.equal(s.el('videos-browse').hidden,true);assert.equal(s.el('videos-detail').hidden,false);
 assert.equal(s.el('videos-selected').textContent,'8화');assert.match(s.location.href,/video=123/);
});
test('favorites are added and removed only through explicit controls',async()=>{
 const s=setup();await s.start();s.el('videos-library').children[0].children[1].onclick();assert.equal(s.favoriteCount(),1);
 s.el('videos-saved').onclick();assert.equal(s.el('videos-library').children.length,1);
 await s.el('videos-library').children[0].children[0].onclick();s.el('videos-detail-save').onclick();assert.equal(s.favoriteCount(),0);
 assert.equal(s.el('videos-detail').hidden,false);assert.equal(s.el('videos-detail-save').attrs['aria-pressed'],'false');
});
test('back restores search and scroll position and destroys the player',async()=>{
 const s=setup();await s.start();s.el('videos-search').value='작품';s.el('videos-search').oninput();
 s.win.scrollY=900;await s.el('videos-library').children[0].children[0].onclick();assert.equal(s.win.scrollY,0);
 s.el('videos-play').onclick();assert.equal(s.el('videos-player').children[0].tag,'iframe');
 s.el('videos-back').onclick();assert.equal(s.el('videos-browse').hidden,false);assert.equal(s.el('videos-detail').hidden,true);
 assert.equal(s.el('videos-search').value,'작품');assert.equal(s.win.scrollY,900);assert.equal(s.location.href,'https://hscope.onrender.com/');
 assert.equal(s.el('videos-player').children.some(x=>x.tag==='iframe'),false);
});
test('episode jump validates availability and next episode continues an active player',async()=>{
 const s=setup();await s.start();await s.el('videos-library').children[0].children[0].onclick();
 assert.equal(s.el('videos-prev').disabled,false);assert.equal(s.el('videos-next').disabled,true);
 s.el('videos-jump').value='7';s.el('videos-jump-form').onsubmit({preventDefault(){}});
 assert.equal(s.el('videos-jump-status').hidden,false);assert.equal(s.el('videos-selected').textContent,'8화');
 s.el('videos-jump').value='1';s.el('videos-jump-form').onsubmit({preventDefault(){}});
 assert.equal(s.el('videos-selected').textContent,'1화');assert.equal(s.el('videos-prev').disabled,true);
 assert.equal(s.el('videos-jump-status').hidden,true);assert.equal(s.el('videos-next').disabled,false);
 s.el('videos-play').onclick();s.el('videos-next').onclick();
 assert.match(s.el('videos-player').children[0].src,/\/k8\/$/);
 assert.equal(s.el('videos-play').disabled,false);assert.equal(s.el('videos-play').textContent,'다시 불러오기');
 assert.equal(s.el('videos-next').disabled,true);
});
