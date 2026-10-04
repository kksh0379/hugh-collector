const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('static/js/videos.js','utf8');
const c=vm.createContext({URL});vm.runInContext(src.slice(src.indexOf('  function parseWatchUrl'),src.indexOf('  let library')),c);
test('watch coordinates preserve title, series and episode',()=>{const v=c.parseWatchUrl('https://linkani.tv/watch/19240/a2/k8/');assert.equal(JSON.stringify(v),JSON.stringify({id:'19240',series:2,episode:8}));assert.equal(c.watchUrl(v),'https://linkani.tv/watch/19240/a2/k8/');});
test('untrusted and malformed addresses are rejected',()=>{for(const url of ['javascript:alert(1)','https://evil.example/watch/19240/a1/k8/','https://linkani.tv.evil.example/watch/19240/a1/k8/','https://user:password@linkani.tv/watch/19240/a1/k8/','http://linkani.tv/watch/19240/a1/k8/','https://linkani.tv/watch/19240/a1/k0/'])assert.equal(c.parseWatchUrl(url),null);});
