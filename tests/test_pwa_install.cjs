const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/pwa-install.js','utf8');
function setup(options={}, state) {
 const button={disabled:false,textContent:'',handlers:{},addEventListener(name,fn){this.handlers[name]=fn;}};
 const card={hidden:true},events={};
 const navigator={userAgent:'Chrome',...options};
 const window={location:{origin:'https://hscope.onrender.com'},HscopeInstallState:state,matchMedia:()=>({matches:false,addEventListener(){}}),addEventListener(name,fn){events[name]=fn;}};
 vm.runInNewContext(source,{window,navigator,URL,document:{getElementById:id=>id==='app-install'?button:id==='install-card'?card:null}});
 return {button,card,events};
}
test('only a real install request enables the installation button',async()=>{
 const s=setup();assert.equal(s.card.hidden,true);assert.equal(s.button.disabled,true);
 await s.button.handlers.click();
 let calls=0;s.events.beforeinstallprompt({preventDefault(){},prompt:async()=>calls++,userChoice:Promise.resolve({outcome:'accepted'})});
 assert.equal(s.card.hidden,false);assert.equal(s.button.disabled,false);
 await s.button.handlers.click();assert.equal(calls,1);assert.equal(s.button.textContent,'설치 완료');assert.equal(s.button.disabled,true);
});
test('early captured install request opens the native confirmation once',async()=>{
 let calls=0;const state={prompt:{prompt:async()=>calls++,userChoice:Promise.resolve({outcome:'dismissed'})}};
 const s=setup({},state);await s.button.handlers.click();await s.button.handlers.click();
 assert.equal(calls,1);assert.equal(state.prompt,null);assert.equal(s.card.hidden,true);
});
test('Web Install API is called directly when supported',async()=>{
 let calls=0;const s=setup({install:async()=>{calls++;}});
 assert.equal(s.card.hidden,false);await s.button.handlers.click();assert.equal(calls,1);
 s.events.appinstalled();assert.equal(s.button.textContent,'설치 완료');assert.equal(s.button.disabled,true);
});
test('native install errors do not open a help popup or display preparation text',async()=>{
 const s=setup();s.events.beforeinstallprompt({preventDefault(){},prompt:async()=>{throw Error('unavailable');}});
 await s.button.handlers.click();assert.equal(s.card.hidden,true);assert.equal(s.button.textContent,'앱 설치');
 assert.doesNotMatch(source,/showModal|alert\(|confirm\(|설치창을 아직|install-guide|install-help|clipboard/);
});
test('standalone app does not offer duplicate installation',async()=>{
 const s=setup({standalone:true});assert.equal(s.card.hidden,false);assert.equal(s.button.disabled,true);
 await s.button.handlers.click();
});
test('manifest targets hscope and icons have their declared dimensions',()=>{
 const m=JSON.parse(fs.readFileSync('static/site.webmanifest','utf8'));
 assert.equal(m.id,'/hscope');assert.equal(m.start_url,'/hscope?app=1');assert.equal(m.orientation,'portrait-primary');assert.equal(m.scope,'/');
 for(const icon of m.icons){const png=fs.readFileSync('.'+icon.src.split('?')[0]),size=Number(icon.sizes.split('x')[0]);assert.equal(png.readUInt32BE(16),size);assert.equal(png.readUInt32BE(20),size);}
});
test('launcher has no installation help or URL copy popup',()=>{
 const html=fs.readFileSync('templates/launcher.html','utf8');
 assert.doesNotMatch(html,/install-help|install-guide|install-copy|install-address|설치 도움말/);
 assert.match(html,/id="install-card"[^>]+hidden/);
});
test('bootstrap keeps early native requests until UI initialization',()=>{
 const events={},window={addEventListener:(name,fn)=>events[name]=fn};
 vm.runInNewContext(fs.readFileSync('static/js/pwa-prompt.js','utf8'),{window});
 const e={preventDefault(){}};events.beforeinstallprompt(e);assert.equal(window.HscopeInstallState.prompt,e);
 events.appinstalled();assert.equal(window.HscopeInstallState.prompt,null);
});
