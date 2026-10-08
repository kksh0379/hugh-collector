const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
test('header uses server display name while ownership retains account ID and logout clears both',()=>{
 const header={textContent:''},bodyClasses=new Set();
 const c=vm.createContext({document:{body:{classList:{toggle:(k,v)=>v?bodyClasses.add(k):bodyClasses.delete(k)}},getElementById:()=>header},applyFeatures:()=>{}});
 const src=fs.readFileSync('static/js/app.js','utf8');vm.runInContext(src.slice(src.indexOf('let AUTH_GENERATION ='),src.indexOf('// ===== 표시 설정')),c);
 vm.runInContext('applyAuthUI("test1", false, "김테스터")',c);assert.equal(header.textContent,'김테스터 님');assert.equal(vm.runInContext('CURRENT_USER',c),'test1');
 vm.runInContext('applyAuthUI(null, false)',c);assert.equal(header.textContent,'');assert.equal(vm.runInContext('CURRENT_USER',c),null);
});
