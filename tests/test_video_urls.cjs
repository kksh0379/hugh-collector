const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('static/js/videos.js','utf8');
const c=vm.createContext({URL});vm.runInContext(src.slice(src.indexOf('  function parseWatchUrl'),src.indexOf('  let library')),c);
test('watch coordinates preserve title, series and episode',()=>{const v=c.parseWatchUrl('https://linkani.tv/watch/19240/a2/k8/');assert.equal(JSON.stringify(v),JSON.stringify({id:'19240',series:2,episode:8}));assert.equal(c.watchUrl(v),'https://linkani.tv/watch/19240/a2/k8/');});
test('untrusted and malformed addresses are rejected',()=>{for(const url of ['javascript:alert(1)','https://evil.example/watch/19240/a1/k8/','https://linkani.tv.evil.example/watch/19240/a1/k8/','https://user:password@linkani.tv/watch/19240/a1/k8/','http://linkani.tv/watch/19240/a1/k8/','https://linkani.tv/watch/19240/a1/k0/'])assert.equal(c.parseWatchUrl(url),null);});
test('existing browsers gain new default works while retaining saved episodes and user additions',()=>{
 const rows=c.mergeLibrary([{id:'19240',series:1,episode:9,title:'강철의 연금술사'},{id:'999',series:2,episode:3,title:'내 작품'},{id:'3217',series:1,episode:100,title:'원피스'}]);
 assert.equal(rows.length,6);assert.equal(rows.find(r=>r.id==='19240').episode,9);assert.equal(rows.find(r=>r.id==='999').series,2);assert.equal(rows.find(r=>r.id==='3217').episode,100);
 assert.equal(JSON.stringify(rows.filter(r=>['21707','2010','70867'].includes(r.id)).map(r=>r.title)),JSON.stringify(['나루토','보루토','바람의 검심']));
});
test('invalid saved data and duplicates cannot hide default works',()=>{const rows=c.mergeLibrary([{id:'3217',series:1,episode:1},{id:'3217',series:1,episode:2},{id:'x',series:1,episode:1}]);assert.equal(rows.length,5);assert.equal(rows.filter(r=>r.id==='3217').length,1);assert.equal(c.mergeLibrary({}).length,5);});
test('search spans the full catalog beyond the visible batch, deduplicates saved titles and respects scope',()=>{
 const works=Array.from({length:500},(_,i)=>({id:String(i+1),title:i===499?'찾을 작품':'작품 '+i})), saved=[{id:'1',title:'내 제목'}];
 assert.equal(c.discoveryRows(saved,works,'all','').length,500);
 assert.equal(c.discoveryRows(saved,works,'all','찾을')[0].id,'500');
 assert.equal(c.discoveryRows(saved,works,'saved','찾을').length,0);
 assert.equal(c.discoveryRows(saved,works,'saved','내 제목').length,1);
});
