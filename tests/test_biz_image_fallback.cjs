const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const code=source.slice(source.indexOf('function thumbnailFallback(image)'),source.indexOf('// 보안뉴스 AI 후처리'));
const context=vm.createContext({escapeHtml:s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;')});
vm.runInContext(code,context);

test('biz images preserve source and retry direct URL only once before fallback',()=>{
  const url='https://example.org/img.jpg';
  const html=context.newsThumb({image_url:url},true);
  assert.match(html,/\/api\/img\?u=/);
  assert.match(html,/data-original-src="https:\/\/example.org\/img.jpg"/);
  const klass={added:[],add(s){this.added.push(s)}};
  const image={dataset:{originalSrc:url},src:'/api/img',alt:'',closest:()=>({classList:klass})};
  context.thumbnailFallback(image);
  assert.equal(image.src,url);
  assert.equal(image.dataset.directAttempted,'1');
  context.thumbnailFallback(image);
  assert.equal(image.src,'/static/no-image.svg');
  assert.equal(image.alt,'이미지 없음');
  assert.deepEqual(klass.added,['is-no-image']);
});

test('image URL markup is escaped and only HTTPS originals are used',()=>{
  const bad='https://example.org/x\" onload=\"evil';
  assert.doesNotMatch(context.newsThumb({image_url:bad},true),/data-original-src="[^"]*" onload=/);
  const html=context.newsThumb({image_url:'http://example.org/img.png'},true);
  assert.doesNotMatch(html,/data-original-src=/);
  const image={dataset:{originalSrc:'http://example.org/img.png'},src:'proxy',closest:()=>({classList:{add(){}}})};
  context.thumbnailFallback(image);
  assert.equal(image.src,'/static/no-image.svg');
});

test('missing image remains an honest no-image placeholder',()=>{
  const html=context.newsThumb({image_url:''},true);
  assert.match(html,/is-no-image/);
  assert.match(html,/\/static\/no-image.svg/);
});

test('combined nonprofit feed keeps thumbnails only for videos',()=>{
  const renderSection=source.slice(source.indexOf('function renderBizCombined('),source.indexOf('function publicationTime('));
  assert.match(renderSection,/hideImage:\s*item\._src\s*!==\s*"video"/);
  assert.match(source,/opts\.hideImage\s*\?\s*""\s*:\s*newsThumb/);
  assert.match(source,/card-no-media/);
});
