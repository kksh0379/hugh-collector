const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/pwa-layout.js','utf8');
function run({installed=false,child=false,url='https://hscope.onrender.com/hscope?video=3217'}={}){
 let replaced;const window={matchMedia:()=>({matches:installed}),location:{href:url,replace:value=>{replaced=value;}}};window.self=window;window.top=child?{}:window;
 vm.runInNewContext(source,{window,navigator:{},URL});return replaced;
}
test('existing installed icon enters portrait shell and preserves video bookmark',()=>{
 const url=new URL(run({installed:true}));assert.equal(url.pathname,'/hscope');assert.equal(url.searchParams.get('app'),'1');assert.equal(url.searchParams.get('video'),'3217');
});
test('normal browser and child frame never get redirected into another shell',()=>{
 assert.equal(run(),undefined);assert.equal(run({installed:true,child:true}),undefined);assert.equal(run({installed:true,url:'https://hscope.onrender.com/hscope?app_frame=1'}),undefined);
});
test('installed shell requests portrait layout but tolerates denied native operations',()=>{
 let resized,locked;const window={matchMedia:q=>({matches:true}),innerWidth:1000,outerWidth:1016,innerHeight:800,outerHeight:840,resizeTo:(...size)=>{resized=size;}};
 const screen={availHeight:900,orientation:{lock:mode=>{locked=mode;return Promise.reject(Error('not supported'));}}};
 vm.runInNewContext(fs.readFileSync('static/js/pwa-shell.js','utf8'),{window,navigator:{},screen});assert.deepEqual(resized,[436,880]);assert.equal(locked,'portrait-primary');
});
test('ordinary browser preview never resizes the user window',()=>{
 vm.runInNewContext(fs.readFileSync('static/js/pwa-shell.js','utf8'),{window:{matchMedia:()=>({matches:false}),resizeTo:()=>{throw Error('must not resize');}},navigator:{}});
});
test('app shell viewport has a mobile maximum width and keeps media permissions',()=>{
 const css=fs.readFileSync('static/css/pwa-shell.css','utf8'),html=fs.readFileSync('templates/pwa_shell.html','utf8');
 assert.match(css,/width:min\(420px,100vw,calc\(100dvh \* .625\)\)/);assert.match(html,/allowfullscreen/);assert.match(html,/clipboard-write; web-share; geolocation/);
});
