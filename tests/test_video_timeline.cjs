const assert = require('node:assert/strict');
const {attach} = require('../static/js/video-timeline.js');
function element() {
  const listeners = new Map();
  return {value:'0', textContent:'', disabled:false, hidden:true,
    setAttribute(){}, addEventListener(e,fn){ if(!listeners.has(e)) listeners.set(e,new Set()); listeners.get(e).add(fn); },
    removeEventListener(e,fn){listeners.get(e)?.delete(fn);}, emit(e){ for(const fn of listeners.get(e)||[]) fn(); }};
}
const video = Object.assign(element(), {duration:120, currentTime:20, paused:false, seeking:false,
  pause(){this.paused=true;this.emit('pause');}, play(){this.paused=false;this.emit('play');return Promise.resolve();}});
const ui = Object.fromEntries(['bar','seek','time','toggle','back','forward','status'].map(k=>[k,element()]));
const controls = attach(video,ui,()=>true);
assert.equal(ui.bar.hidden,false); assert.equal(ui.time.textContent,'0:20 / 2:00');
let seeks=0, position=20;
Object.defineProperty(video,'currentTime',{get:()=>position,set:value=>{seeks++;position=value;video.seeking=true;}});
ui.seek.value='90';ui.seek.emit('input');
position=22;video.emit('timeupdate');
assert.equal(ui.seek.value,'90'); assert.equal(seeks,0,'dragging sends no remote seeks');
ui.seek.emit('change');assert.equal(seeks,1);assert.equal(position,90);assert.equal(controls.pending(),true);
position=25;video.emit('timeupdate');assert.equal(ui.seek.value,'90','delayed receiver updates cannot snap the slider back');
position=90;video.seeking=false;video.emit('seeked');assert.equal(controls.pending(),false);assert.equal(ui.status.textContent,'');
ui.forward.emit('click');assert.equal(position,100);position=100;video.seeking=false;video.emit('seeked');
ui.seek.value='500';ui.seek.emit('change');assert.equal(position,119.9,'seeks clamp to duration');video.seeking=false;video.emit('seeked');
ui.toggle.emit('click');assert.equal(video.paused,true);assert.equal(ui.toggle.textContent,'재생');
controls.destroy();assert.equal(ui.bar.hidden,true);const count=seeks;ui.forward.emit('click');assert.equal(seeks,count,'cleanup removes old player bindings');
console.log('Video timeline: drag, delayed AirPlay acknowledgement, bounds, pause and cleanup passed.');
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync(require.resolve('../static/js/videos.js'),'utf8');
const metadata = source.slice(source.indexOf('video.onloadedmetadata = () => {'),source.indexOf('video.ontimeupdate ='));
const scope = {video:{duration:120,currentTime:0,setAttribute(){}},progress:{work:{seconds:40}},item:{id:'work'},current:()=>true,singleSubtitle(){},resumeRestored:false};
vm.runInNewContext(metadata,scope);scope.video.onloadedmetadata();assert.equal(scope.video.currentTime,40);
scope.video.currentTime=90;scope.video.onloadedmetadata();assert.equal(scope.video.currentTime,90,'AirPlay metadata cannot restore an old resume position again');
console.log('Resume position: repeated AirPlay metadata preserves the current position.');
