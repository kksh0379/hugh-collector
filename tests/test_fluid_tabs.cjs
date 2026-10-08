const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const css=fs.readFileSync('static/css/style.css','utf8');
const html=fs.readFileSync('templates/index.html','utf8');
test('top navigation wraps based on available width, without fixed rows or breakpoint',()=>{
  assert.match(css,/\.tabs\s*\{[^}]*flex-wrap:wrap;/);
  assert.doesNotMatch(css,/tabs-row|max-width:959px/);
  assert.doesNotMatch(html,/tabs-row/);
  const nav=html.match(/<nav class="tabs" id="tabs">([\s\S]*?)<\/nav>/)[1];
  assert.equal((nav.match(/<button /g)||[]).length,6);
  assert.doesNotMatch(nav,/<div/);
});
test('tabs preserve intrinsic width, compact height, single-line labels and icons',()=>{
  assert.match(css,/\.tabs > \.tab\s*\{[^}]*height:30px;[^}]*flex:0 0 auto;[^}]*white-space:nowrap;/);
  assert.match(css,/\.tabs > \.tab \.tab-icon\s*\{[^}]*width:16px;[^}]*height:16px;/);
});
