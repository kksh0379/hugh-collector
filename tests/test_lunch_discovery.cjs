const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/app.js','utf8');
const filtered = source.slice(source.indexOf('  function filtered() {'),source.indexOf('  function stars(avg) {'));
function context() {
 const LUNCH = {cat:'전체',q:'',reviewedOnly:false,walkMin:10,sort:'random',rows:[
  {id:1,name:'첫 식당',dist_m:100,avg_rating:3},
  {id:2,name:'둘 식당',dist_m:600,avg_rating:5},
  {id:3,name:'셋 식당',dist_m:1100,avg_rating:4}]};
 const ctx = vm.createContext({LUNCH,randomRanks:new Map([['1',.8],['2',.1],['3',.5]])});
 vm.runInContext(filtered,ctx); return ctx;
}
test('walking time filters by the precise radius before rounding displayed minutes',()=>{
 const ctx=context();
 for (const [minutes,expected] of [[5,[1]],[10,[2,1]],[15,[2,1]],[20,[2,3,1]]]) {
  ctx.LUNCH.walkMin=minutes; assert.deepEqual(Array.from(ctx.filtered(),r=>r.id),expected);
 }
});
test('random order stays stable when re-rendering and never mutates stored rows',()=>{
 const ctx=context();
 assert.deepEqual(Array.from(ctx.filtered(),r=>r.id),[2,1]);
 assert.deepEqual(Array.from(ctx.filtered(),r=>r.id),[2,1]);
 assert.deepEqual(ctx.LUNCH.rows.map(r=>r.id),[1,2,3]);
 ctx.LUNCH.sort='distance'; assert.deepEqual(Array.from(ctx.filtered(),r=>r.id),[1,2]);
 ctx.LUNCH.sort='rating'; assert.deepEqual(Array.from(ctx.filtered(),r=>r.id),[2,1]);
});
test('removed restaurant photo scraping stays disabled',()=>{
 const app=fs.readFileSync('app.py','utf8');
 assert.ok(!app.includes('/api/lunch/images'));
 assert.ok(!source.includes('HScopeLunchGallery?.mount(list)'));
});
