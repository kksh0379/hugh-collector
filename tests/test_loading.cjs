const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/app.js', 'utf8');
const ctx = vm.createContext({escapeHtml: s => String(s).replaceAll('<', '&lt;').replaceAll('>', '&gt;')});
vm.runInContext(source.slice(source.indexOf('function catRunSvg'), source.indexOf('function showLoading')), ctx);
test('every loader always includes both breeds and an accessible status', () => {
  for (const fn of ['catSpin', 'catRunInline']) {
    const html = vm.runInContext(`${fn}('불러오는 중…')`, ctx);
    assert.match(html, /koshort/);
    assert.match(html, /chinchilla/);
    assert.match(html, /role="status"/);
    assert.match(html, /aria-hidden="true"/);
  }
});
test('loader progress labels cannot inject HTML', () => {
  assert.doesNotMatch(vm.runInContext('catRunInline("<script>alert(1)</script>")',ctx), /<script>/);
});
test('old random and mini spinners are no longer emitted', () => {
  assert.doesNotMatch(source, /class="mini-spin"|class="catrun/);
});
test('loader uses isolated animated image and a reduced-motion still source', () => {
  const html = vm.runInContext('catSpin()', ctx);
  assert.match(html, /<picture>/);
  assert.match(html, /prefers-reduced-motion: reduce/);
  assert.match(html, /srcset="data:image\/webp;base64,/);
  assert.match(html, /class="cat-still" src="data:image\/webp;base64,/);
  assert.match(html, /cats-loading-smooth-v2.28.webp/);
  const css = fs.readFileSync('static/css/style.css', 'utf8');
  assert.doesNotMatch(css, /background-size:400%|step-end|@keyframes kitten-frames/);
  assert.match(css, /overflow:hidden/);
});
test('wheel is inline CSS, cats remain visible while animation downloads', () => {
  const html = vm.runInContext('catSpin()', ctx);
  assert.match(html, /cat-wheel-tread/);
  assert.doesNotMatch(html, /cat-orbit/);
  assert.match(html, /fetchpriority="high"/);
  const css = fs.readFileSync('static/css/style.css','utf8');
  assert.match(css, /\.cat-frames \{ opacity:0; \}/);
  assert.match(css, /\.cat-frames\.is-ready \+ \.cat-still \{ display:none; \}/);
  assert.match(css, /\.cat-wheel-tread \{ animation:none; \}/);
  assert.match(source, /img\.naturalWidth > 0/);
  const template=fs.readFileSync('templates/index.html','utf8');
  assert.match(template, /fetchpriority="high"[^]*?cats-loading-smooth-v2\.28\.webp/);
  assert.doesNotMatch(template, /rel="preload"[^\n]*slot-chinchilla/);
});
