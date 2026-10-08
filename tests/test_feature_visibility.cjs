const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/app.js', 'utf8');
function functionSource(name) {
  const start = source.indexOf('function ' + name + '(');
  let end = source.indexOf('{', start), depth = 1;
  for (++end; depth; ++end) { if (source[end] === '{') ++depth; if (source[end] === '}') --depth; }
  return source.slice(start, end);
}
test('hidden integrated sources disappear for visitors and remain visible to admins', () => {
  const ctx = vm.createContext({ FEATURES: {boards:false, social:false}, bizSrc:new Set(['news','board','video']), document:{body:{classList:{contains:()=>false}}} });
  vm.runInContext(functionSource('featureHidden') + functionSource('filterBizBySrc'),ctx);
  const items = [{_src:'news'},{_src:'board'},{_src:'video'}];
  assert.deepEqual(Array.from(ctx.filterBizBySrc(items), x=>x._src), ['news']);
  ctx.document.body.classList.contains=()=>true;
  assert.equal(ctx.filterBizBySrc(items).length,3);
  ctx.bizSrc=new Set(['board']);
  assert.deepEqual(Array.from(ctx.filterBizBySrc(items), x=>x._src), ['board']);
});
test('hidden active main menu returns to news and admin sees all menus', () => {
  const elements = Object.fromEntries(['food','videos','finance','report','scrap'].map(k=>[k,{hidden:false}]));
  let admin=false, destination;
  const ctx=vm.createContext({ FEATURES:{food:false,videos:false,finance:false}, FEATURE_TABS:[], FEATURE_MAIN:Object.keys(elements), FEATURE_ALL:Object.keys(elements), TAB_DATA:{}, localStorage:{setItem(){}}, window:{gotoView:n=>destination=n}, document:{documentElement:{classList:{remove(){}}},body:{classList:{contains:()=>admin,toggle(){}}},getElementById:()=>null,querySelector:s=>s==='.fnav.active'?elements.food:(elements[/data-nav="([^"]+)"/.exec(s)?.[1]]||null)} });
  vm.runInContext(functionSource('applyFeatures'),ctx);
  ctx.applyFeatures();
  assert.equal(elements.food.hidden,true);
  assert.equal(elements.videos.hidden,true);
  assert.equal(elements.finance.hidden,true);
  assert.equal(destination,'collector');
  admin=true;
  ctx.applyFeatures();
  assert.equal(elements.food.hidden,false);
  assert.equal(elements.videos.hidden,false);
});
