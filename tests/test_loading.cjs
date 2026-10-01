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
test('sprite playback visits all sixteen cells discretely and loops to the first pose', () => {
  const css = fs.readFileSync('static/css/style.css', 'utf8');
  const frames = css.match(/@keyframes kitten-frames \{([\s\S]*?)\n\}/)[1];
  const positions = [...frames.matchAll(/background-position:([^;]+);/g)].map(m => m[1]);
  assert.equal(positions.length, 17);
  assert.equal(new Set(positions.slice(0, 16)).size, 16);
  assert.equal(positions[16], positions[0]);
  assert.match(css, /background-size:400% 400%/);
  assert.match(css, /kitten-frames 2\.4s step-end infinite/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.doesNotMatch(css, /kitten-hop/);
});
