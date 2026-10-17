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
const {photoUrls,safeUrl}=require('../static/js/lunch-gallery.js');
test('gallery only renders verified safe photos, with deduplication and a three-photo cap',()=>{
 const data={status:'verified',verification:'business_name_address',source_url:'https://example.com/store',images:['https://example.com/a.jpg','javascript:alert(1)','https://example.com/a.jpg','https://example.com/b.jpg','https://example.com/c.jpg','https://example.com/d.jpg']};
 assert.equal(photoUrls(data).length,3);
 assert.equal(photoUrls({...data,status:'pending'}).length,0);
 assert.equal(photoUrls({...data,verification:'guess'}).length,0);
 assert.equal(photoUrls({...data,source_url:'javascript:alert(1)'}).length,0);
 assert.equal(safeUrl('https://user:password@example.com/'),'');
});
test('gallery overflow stays within the card and uses horizontal snapping, not automatic scrolling',()=>{
 const css=fs.readFileSync('static/css/style.css','utf8');
 assert.match(css,/\.lunch-card\{min-width:0;overflow:hidden\}/);
 assert.match(css,/\.lunch-photo-rail\{[^}]*overflow-x:auto[^}]*scroll-snap-type:x mandatory/);
 assert.match(source,/HScopeLunchGallery\?\.mount\(list\)/);
});
