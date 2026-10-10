const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
test('header omits the display name while account ownership and logout state remain correct',()=>{
 const header={textContent:''},bodyClasses=new Set();
 const c=vm.createContext({document:{body:{classList:{toggle:(k,v)=>v?bodyClasses.add(k):bodyClasses.delete(k)}},getElementById:()=>{throw Error('name must not be written into header');}},applyFeatures:()=>{}});
 const src=fs.readFileSync('static/js/app.js','utf8');vm.runInContext(src.slice(src.indexOf('let AUTH_GENERATION ='),src.indexOf('// ===== 표시 설정')),c);
 vm.runInContext('applyAuthUI("test1", false, "김테스터")',c);assert.equal(header.textContent,'');assert.equal(vm.runInContext('CURRENT_USER',c),'test1');assert.equal(bodyClasses.has('is-loggedin'),true);
 vm.runInContext('applyAuthUI(null, false)',c);assert.equal(header.textContent,'');assert.equal(vm.runInContext('CURRENT_USER',c),null);assert.equal(bodyClasses.has('is-loggedin'),false);
});
