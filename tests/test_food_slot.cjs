const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/app.js', 'utf8');
const helpers = source.slice(source.indexOf('function foodSlotHtml'), source.indexOf('function showLoading'));
test('food loader repeats a complete food cycle and clips three independent reels', () => {
  const ctx = vm.createContext({}); vm.runInContext(helpers, ctx);
  const html = ctx.foodSlotHtml();
  assert.equal((html.match(/class="slot-reel"/g) || []).length, 3);
  assert.equal((html.match(/class="slot-tile"/g) || []).length, 36);
  assert.match(html, /role="status"/);
  assert.doesNotMatch(html, /cat-pair/);
  const css = fs.readFileSync('static/css/style.css', 'utf8');
  assert.match(css, /food-reel \.72s linear infinite/);
  assert.match(css, /translate3d\(0,-336px,0\)/);
});
test('response stops all reels at an exact food cell in staggered order', async () => {
  const calls = [];
  const tracks = [0,1,2].map(i => ({style:{}, animate:(frames, options) => {calls.push({i,frames,options});return {finished:Promise.resolve()};}}));
  const ctx = vm.createContext({window:{matchMedia:()=>({matches:false})},getComputedStyle:()=>({transform:'matrix(1,0,0,1,0,-120)'})});
  vm.runInContext(helpers, ctx);
  await ctx.settleFoodSlot({querySelector:()=>({textContent:''}),querySelectorAll:()=>tracks}, '돈가스');
  assert.deepEqual(calls.map(c=>c.options.duration), [500,600,700]);
  for (const c of calls) assert.equal(c.frames[1].transform, 'translate3d(0,-840px,0)');
});
test('late recommendation responses cannot replace a newer recommendation', async () => {
  const pending = [], rendered = [];
  const ctx = vm.createContext({recommendationRequest:0,LUNCH:{curLoc:{id:1},rows:[{id:1}],aiPersona:''},showView:()=>{},$:()=>({innerHTML:''}),foodSlotHtml:()=>'',gatherConditions:()=>({avoid_cats:[],moods:[]}),api:()=>new Promise(resolve=>pending.push(resolve)),settleFoodSlot:async()=>{},renderRecommend:r=>rendered.push(r.pick.name)});
  vm.runInContext(source.slice(source.indexOf('  async function runRecommend()'), source.indexOf('  function renderRecommend(res)')), ctx);
  const first = ctx.runRecommend(), second = ctx.runRecommend();
  pending[1]({ok:true,pick:{name:'new',cat_norm:'한식'}}); await second;
  pending[0]({ok:true,pick:{name:'old',cat_norm:'한식'}}); await first;
  assert.deepEqual(rendered,['new']);
});
