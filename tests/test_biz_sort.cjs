const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const ctx=vm.createContext({});
vm.runInContext(source.slice(source.indexOf('function publicationTime'),source.indexOf('let _bizBoards')),ctx);
const ids=rows=>Array.from(rows,it=>it.id);
test('October news precedes September compact board date across all sources',()=>{
 const rows=ctx.mergeBiz([{id:'news',published_at:'2026-10-04 02:29'}], [{id:'board',published_at:'20260921'}], [{id:'video',published_at:'2026-10-02T09:13:00'}]);
 assert.deepEqual(ids(rows),['news','video','board']);
 assert.equal(rows[0]._src,'news');assert.equal(rows[1]._src,'video');
});
test('same-day time, year boundary, and undated items sort consistently',()=>{
 const rows=ctx.mergeBiz([{id:'new',published_at:'2026-01-01 01:00'},{id:'bad',published_at:'unknown'}], [{id:'day',published_at:'20260101'},{id:'old',published_at:'20251231'},{id:'missing',published_at:null}],[]);
 assert.deepEqual(ids(rows),['new','day','old','bad','missing']);
});
test('timezone offsets compare chronologically and equal instants remain stable',()=>{
 const rows=ctx.mergeBiz([{id:'a',published_at:'2026-10-04T12:00:00Z'}], [{id:'b',published_at:'2026-10-04T21:00:00+09:00'}], [{id:'c',published_at:'2026-10-04T22:00:00+09:00'}]);
 assert.deepEqual(ids(rows),['c','a','b']);
});
