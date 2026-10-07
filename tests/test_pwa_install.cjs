const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/pwa-install.js','utf8');
function setup(options={}) {
  function element(){return {handlers:{},textContent:'',value:'',children:[],disabled:false,addEventListener(name,fn){this.handlers[name]=fn;},replaceChildren(){this.children=[];},append(node){this.children.push(node);},focus(){this.focused=true;},select(){this.selected=true;}};}
  const ids={};for(const id of ['app-install','install-status','install-steps','install-address','install-description','install-copy'])ids[id]=element();
  const close=element(),dialog={...element(),open:false,showModal(){this.open=true;},close(){this.open=false;this.handlers.close?.();},querySelector:()=>close};ids['install-guide']=dialog;
  const events={},media={matches:false,addEventListener(){}};
  const navigator={userAgent:'Chrome Windows',platform:'Win32',maxTouchPoints:0,clipboard:{writeText:async()=>{}},...options};
  const ctx=vm.createContext({navigator,document:{getElementById:id=>ids[id],createElement:()=>element()},window:{matchMedia:()=>media,location:{origin:'https://hscope.onrender.com'},addEventListener(name,fn){events[name]=fn;}}});
  vm.runInContext(source,ctx);return {ids,dialog,events,ctx};
}
test('native install prompt is deferred until user clicks and cancellation reenables button',async()=>{
  const s=setup();let prevented=false,calls=0;
  s.events.beforeinstallprompt({preventDefault(){prevented=true;},prompt:async()=>calls++,userChoice:Promise.resolve({outcome:'dismissed'})});
  assert.ok(prevented);assert.equal(calls,0);await s.ids['app-install'].handlers.click();assert.equal(calls,1);assert.equal(s.ids['app-install'].disabled,false);
});
test('accepted installation shows completion and appinstalled closes guide',async()=>{
  const s=setup();s.events.beforeinstallprompt({preventDefault(){},prompt:async()=>{},userChoice:Promise.resolve({outcome:'accepted'})});
  await s.ids['app-install'].handlers.click();assert.equal(s.ids['app-install'].textContent,'설치 완료');assert.equal(s.ids['app-install'].disabled,true);
  s.dialog.showModal();s.events.appinstalled();assert.equal(s.dialog.open,false);
});
test('iPhone shows Safari home screen instructions with root launcher URL',async()=>{
  const s=setup({userAgent:'iPhone Safari'});assert.equal(s.ids['app-install'].textContent,'홈 화면에 추가');await s.ids['app-install'].handlers.click();
  assert.equal(s.dialog.open,true);assert.match(s.ids['install-steps'].children[1].textContent,/홈 화면에 추가/);assert.equal(s.ids['install-address'].value,'https://hscope.onrender.com/');
});
test('installed iOS app does not offer another installation',async()=>{
  const s=setup({standalone:true});assert.equal(s.ids['app-install'].disabled,true);await s.ids['app-install'].handlers.click();assert.equal(s.dialog.open,false);
});
test('clipboard failure selects launcher address for manual copying',async()=>{
  const s=setup({clipboard:{writeText:async()=>{throw Error();}}});await s.ids['app-install'].handlers.click();await s.ids['install-copy'].handlers.click();assert.equal(s.ids['install-address'].selected,true);assert.match(s.ids['install-status'].textContent,/복사/);
});
test('manifest starts at launcher and raster app icons have declared dimensions',()=>{
  const manifest=JSON.parse(fs.readFileSync('static/site.webmanifest','utf8'));assert.equal(manifest.start_url,'/');assert.equal(manifest.id,'/');assert.equal(manifest.display,'standalone');
  for(const icon of manifest.icons){const png=fs.readFileSync('.'+icon.src);const size=Number(icon.sizes.split('x')[0]);assert.equal(png.readUInt32BE(16),size);assert.equal(png.readUInt32BE(20),size);}
});
