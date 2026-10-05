const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/videos.js','utf8');
const flush=()=>new Promise(setImmediate);
function setup(direct = false, episodes = [1,8], options = {}) {
 const elements=new Map(), stored=new Map([['hscope-video-library-v1',JSON.stringify([{id:'123',series:1,episode:8,title:'작품 A'}])]]), listeners={};
 function element(tag='div') { return {tag,webkitShowPlaybackTargetPicker:options.airplay && tag==='video' ? function(){this.pickerCount=(this.pickerCount||0)+1} : undefined,open:false,style:{setProperty(k,v){this[k]=v}},children:[],dataset:{},attrs:{},value:'',textContent:'',hidden:false,setAttribute(k,v){this.attrs[k]=v},append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=nodes},querySelectorAll(){return this.children.filter(x=>x.tag==='button')},querySelector(tag){return this.children.find(x=>tag.split(',').map(x=>x.trim()).includes(x.tag))||null},addEventListener(k,v){const previous=this['on'+k];this['on'+k]=(...args)=>{previous?.(...args);v(...args)}},getBoundingClientRect(){return {bottom:440,left:0,right:400,top:400}},showModal(){this.open=true},close(){this.open=false},focus(){},remove(){},pause(){},load(){},removeAttribute(k){delete this.attrs[k]},canPlayType(){return direct?'probably':''},play(){this.playCount=(this.playCount||0)+1;return Promise.resolve()}}; }
 const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
 el('videos-detail').hidden=true;el('videos-detail-body').hidden=true;
 const location={href:'https://hscope.onrender.com/'}, entries=[{url:location.href,state:null}];let position=0;
 const win={requestAnimationFrame:callback=>setImmediate(callback),removeEventListener(name,fn){if(listeners[name]===fn)delete listeners[name]},innerHeight:844,scrollY:900,scrollTo(x,y){this.scrollY=typeof x==='object'?x.top:y},addEventListener(name,fn){listeners[name]=fn}};
 const history={state:null,pushState(state,unused,url){entries.splice(++position);entries.push({state,url:String(url)});this.state=state;location.href=String(url)},replaceState(state,unused,url){entries[position]={state,url:String(url)};this.state=state;location.href=String(url)},back(){if(position){const entry=entries[--position];this.state=entry.state;location.href=entry.url;listeners.popstate()}}};
 const works=[{id:'123',series:1,episode:1,title:'작품 A'},{id:'456',series:1,episode:1,title:'작품 B'}];
 const c=vm.createContext({URL,AbortController,location,history,window:win,document:{documentElement:{style:{overflow:''}},getElementById:el,createElement:element},localStorage:{getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v)},setTimeout:()=>1,clearTimeout(){},fetch:async url=>({ok:!url.includes('/playback')||(direct&&!options.missing),json:async()=>url.includes('/playback')?(options.missing ? {code:'video_missing',error:'원출처에 영상이 없어요.'} : {src:'https://aniplayer1.site/test.m3u8',tracks:options.subtitles?[{src:'https://aniplayer1.site/sub.vtt'}]:[],...(options.subtitles?{native_src:'https://hscope.onrender.com/api/videos/native.m3u8?token=test'}:{})}):url.includes('/library')?{items:works}:{id:'123',title:'작품 A',series:[{id:1,episodes}]}})});
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
 await s.el('videos-play').onclick();assert.equal(s.el('videos-player').children[0].tag,'iframe');
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
 await s.el('videos-play').onclick();s.el('videos-next').onclick();await flush();
 assert.match(s.el('videos-player').children[0].src,/\/k8\/#linktv-video$/);
 assert.equal(s.el('videos-play').disabled,false);assert.equal(s.el('videos-resume-title').textContent,'다시 불러오기');
 assert.equal(s.el('videos-next').disabled,true);
});

test('direct video replaces the entire source page and is destroyed on navigation',async()=>{
 const s=setup(true);await s.start();await s.el('videos-library').children[0].children[0].onclick();
 await s.el('videos-play').onclick();const video=s.el('videos-player').children[0];
 assert.equal(video.tag,'video');assert.equal(video.controls,true);assert.equal(video.playsInline,true);
 assert.equal(video.src,'https://aniplayer1.site/test.m3u8');
 s.el('videos-back').onclick();assert.equal(s.el('videos-player').children.some(x=>x.tag==='video'),false);
});

test('episode sheet opens at current episode; choosing closes it and starts playback without scrolling',async()=>{
 const s=setup(true);await s.start();await s.el('videos-library').children[0].children[0].onclick();
 s.win.scrollY=120;s.el('videos-picker-open').onclick();
 assert.equal(s.el('videos-picker').open,true);assert.equal(s.el('videos-picker-open').attrs['aria-expanded'],'true');
 assert.equal(s.el('videos-picker-open').textContent,'8화 ▾');
 s.el('videos-episodes').children[0].onclick();await flush();
 assert.equal(s.el('videos-picker').open,false);assert.equal(s.win.scrollY,120);
 assert.equal(s.el('videos-picker-open').textContent,'1화 ▾');assert.equal(s.el('videos-player').children[0].tag,'video');
});
test('invalid jump keeps sheet open; close and escape preserve playback',async()=>{
 const s=setup(true);await s.start();await s.el('videos-library').children[0].children[0].onclick();
 await s.el('videos-play').onclick();const video=s.el('videos-player').children[0];
 s.el('videos-picker-open').onclick();s.el('videos-jump').value='7';s.el('videos-jump-form').onsubmit({preventDefault(){}});
 assert.equal(s.el('videos-picker').open,true);assert.equal(s.el('videos-player').children[0],video);
 s.el('videos-picker').oncancel({preventDefault(){}});assert.equal(s.el('videos-picker').open,false);
 assert.equal(s.el('videos-player').children[0],video);
 s.el('videos-picker-open').onclick();s.el('videos-back').onclick();assert.equal(s.el('videos-picker').open,false);
});
test('playback time is saved for the same episode and cleared when selecting another',async()=>{
 const s=setup(true);await s.start();await s.el('videos-library').children[0].children[0].onclick();
 await s.el('videos-play').onclick();const video=s.el('videos-player').children[0];video.currentTime=204;video.ontimeupdate();
 assert.equal(JSON.parse(s.stored.get('hscope-video-progress-v1'))['123'].seconds,204);
 assert.equal(s.el('videos-resume-info').textContent,'8화 · 3:24');
 s.el('videos-prev').onclick();await flush();
 assert.equal(JSON.parse(s.stored.get('hscope-video-progress-v1'))['123'].seconds,0);
 assert.equal(s.el('videos-resume-info').textContent,'1화');
});

test('1179 episodes use 100-episode ranges, current/latest shortcuts and whole-series numeric jump',async()=>{
 const episodes=Array.from({length:1179},(_,i)=>i+1),s=setup(true,episodes);
 await s.start();await s.el('videos-library').children[0].children[0].onclick();
 assert.equal(s.el('videos-range').children.length,12);
 assert.equal(s.el('videos-episodes').children.length,100);
 s.el('videos-picker-open').onclick();s.el('videos-latest-page').onclick();
 assert.equal(s.el('videos-range').value,'1101');assert.equal(s.el('videos-episodes').children.length,79);
 assert.equal(s.el('videos-episodes').children.at(-1).textContent,'1179화');
 assert.equal(s.el('videos-selected').textContent,'8화');
 s.el('videos-range-prev').onclick();assert.equal(s.el('videos-range').value,'1001');
 s.el('videos-current-page').onclick();assert.equal(s.el('videos-range').value,'1');
 s.el('videos-jump').value='1179';s.el('videos-jump-form').onsubmit({preventDefault(){}});await flush();
 assert.equal(s.el('videos-selected').textContent,'1179화');assert.equal(s.el('videos-next').disabled,true);
 assert.equal(s.el('videos-range').value,'1101');assert.equal(s.el('videos-picker').open,false);
 assert.equal(s.el('videos-player').children[0].tag,'video');
});
test('sparse episodes create only populated ranges and hide range selector for a short series',async()=>{
 const s=setup(true,[1,1001,1179]);await s.start();await s.el('videos-library').children[0].children[0].onclick();
 assert.equal(s.el('videos-range').children.length,3);s.el('videos-latest-page').onclick();
 assert.equal(s.el('videos-episodes').children.length,1);assert.equal(s.el('videos-episodes').children[0].textContent,'1179화');
 const short=setup();await short.start();await short.el('videos-library').children[0].children[0].onclick();
 assert.equal(short.el('videos-range-row').hidden,true);assert.equal(short.el('videos-series-label').hidden,true);
});

test('missing source episode shows a clear message and never loads an iframe',async()=>{
 const s=setup(true,[1,8],{missing:true});await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();
 assert.equal(s.el('videos-player').children[0].tag,'p');assert.match(s.el('videos-player').children[0].textContent,/영상이 없어요/);assert.equal(s.el('videos-resume-title').textContent,'다시 확인하기');
});
test('AirPlay picker stays available after cancellation and supports return to device',async()=>{
 const s=setup(true,[1,8],{airplay:true});await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();
 const video=s.el('videos-player').children[0];assert.equal(s.el('videos-airplay-controls').hidden,false);
 s.el('videos-airplay').onclick();video.onwebkitplaybacktargetavailabilitychanged({availability:'not-available'});
 assert.equal(s.el('videos-airplay-controls').hidden,false);assert.equal(s.el('videos-airplay').disabled,false);
 video.webkitCurrentPlaybackTargetIsWireless=true;video.onwebkitcurrentplaybacktargetiswirelesschanged();assert.equal(s.el('videos-airplay-return').hidden,false);
 s.el('videos-airplay-return').onclick();assert.equal(video.pickerCount,2);assert.match(s.el('videos-airplay-status').textContent,/이 기기/);
 video.webkitCurrentPlaybackTargetIsWireless=false;video.onwebkitcurrentplaybacktargetiswirelesschanged();assert.equal(s.el('videos-airplay-return').hidden,true);assert.equal(s.el('videos-airplay').textContent,'AirPlay');
});
test('native subtitle rendition is used instead of page-only tracks',async()=>{
 const s=setup(true,[1,8],{subtitles:true});await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();
 const video=s.el('videos-player').children[0];assert.match(video.src,/native\.m3u8/);assert.equal(video.children.length,0);
});
test('media errors display unavailable status instead of silently switching to source page',async()=>{
 const s=setup(true);await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();s.el('videos-player').children[0].onerror();
 assert.equal(s.el('videos-player').children[0].tag,'p');assert.match(s.el('videos-detail-status').textContent,/제공이 중단/);
});

test('native controls recover after AirPlay cancellation without replacing video or changing playback',async()=>{
 const s=setup(true,[1,8],{airplay:true});await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();
 const video=s.el('videos-player').children[0];video.currentTime=204;const src=video.src;
 video.onwebkitplaybacktargetavailabilitychanged({availability:'not-available'});assert.equal(video.controls,false);
 await flush();await flush();assert.equal(video.controls,true);assert.equal(s.el('videos-player').children[0],video);assert.equal(video.src,src);assert.equal(video.currentTime,204);
 video.webkitCurrentPlaybackTargetIsWireless=true;video.onwebkitcurrentplaybacktargetiswirelesschanged();assert.equal(video.controls,true);
 video.webkitCurrentPlaybackTargetIsWireless=false;video.onwebkitcurrentplaybacktargetiswirelesschanged();await flush();await flush();assert.equal(video.controls,true);
});
test('native controls are not rebuilt during fullscreen',async()=>{
 const s=setup(true,[1,8],{airplay:true});await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();
 const video=s.el('videos-player').children[0];video.webkitDisplayingFullscreen=true;video.onwebkitplaybacktargetavailabilitychanged({availability:'available'});assert.equal(video.controls,true);
 video.webkitDisplayingFullscreen=false;video.onwebkitendfullscreen();await flush();await flush();assert.equal(video.controls,true);
});
test('manual player repair recreates controls at exact saved time without changing episode or paused state',async()=>{
 const s=setup(true,[1,8],{airplay:true});await s.start();await s.el('videos-library').children[0].children[0].onclick();await s.el('videos-play').onclick();
 const old=s.el('videos-player').children[0];old.currentTime=204.5;old.paused=true;s.el('videos-player-repair').onclick();await flush();
 const video=s.el('videos-player').children[0];assert.notEqual(video,old);assert.equal(video.controls,true);video.duration=1000;video.onloadedmetadata();assert.equal(video.currentTime,204.5);assert.equal(video.playCount||0,0);assert.equal(s.el('videos-selected').textContent,'8화');
});
