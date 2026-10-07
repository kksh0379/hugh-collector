const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const helpers=source.slice(source.indexOf('function mdToHtml'),source.indexOf('// 관리자 패치내역 표시'));
const ctx=vm.createContext({});vm.runInContext(helpers,ctx);
const markdown=fs.readFileSync('CHANGELOG.md','utf8');
test('all version headings become accordion rows with their own detail',()=>{
 const html=ctx.renderChangelog(markdown);
 const headings=markdown.split('\n').filter(line=>line.startsWith('### '));
 assert.equal((html.match(/<details class="cl-item">/g)||[]).length,headings.length);
 for(let v=10;v<=51;v++){
  const version=`v2.${String(v).padStart(2,'0')}`;
  const row=html.match(new RegExp(`<details class="cl-item"><summary>${version.replace('.','\\.')} · [\\s\\S]*?</details>`));
  assert.ok(row,version);assert.match(row[0],/<div class="cl-body"><ul><li>/);
 }
 assert.match(html,/v2\.08 · 260928/);assert.match(html,/리더뷰 · 261001/);
 assert.doesNotMatch(markdown,/^## .*v2\./m);
});
test('details preserve bullet separation, bold and inline code',()=>{
 const html=ctx.renderChangelog('## 2026-10-02\n### v2.43 · 261002 — 정리\n- **첫 항목**: 설명\n- 두 번째 `코드`\n');
 assert.equal((html.match(/<li>/g)||[]).length,2);assert.match(html,/<strong>첫 항목<\/strong>/);assert.match(html,/<code>코드<\/code>/);
});
test('patch content is escaped before formatting',()=>{
 const html=ctx.renderChangelog('### v2.43 — <img src=x onerror=alert(1)>\n- **<script>alert(1)</script>**\n');
 assert.doesNotMatch(html,/<img|<script/);assert.match(html,/&lt;img/);assert.match(html,/<strong>&lt;script/);
});
test('note links are clickable but unsafe schemes and HTML remain inert',()=>{
 const html=ctx.mdToHtml('[관리](https://example.com/settings?a=1&b=2) [위험](javascript:alert(1)) <img src=x onerror=alert(1)> `https://example.com`');
 assert.match(html,/<a href="https:\/\/example.com\/settings\?a=1&amp;b=2" target="_blank" rel="noopener noreferrer">관리<\/a>/);
 assert.doesNotMatch(html,/<a href="javascript:|<img/);
 assert.match(html,/&lt;img/);
 assert.match(html,/<code>https:\/\/example.com<\/code>/);
 const quoted=ctx.mdToHtml('[주소](https://example.com/" onclick="alert(1))');
 assert.doesNotMatch(quoted,/<a| onclick="/);
});
test('integration tables keep links and escape cells without swallowing the next section',()=>{
 const html=ctx.mdToHtml('| 서비스 | 링크 |\n| --- | --- |\n| Render | [관리](https://dashboard.render.com/) |\n| <script> | `KEY` |\n\n## 다음 절\n본문');
 assert.match(html,/<div class="notes-table-wrap"><table><thead>/);
 assert.equal((html.match(/<th scope="col">/g)||[]).length,2);
 assert.equal((html.match(/<td>/g)||[]).length,4);
 assert.match(html,/<a href="https:\/\/dashboard.render.com\/"/);
 assert.doesNotMatch(html,/<script>/);
 assert.match(html,/<\/table><\/div><h3>다음 절<\/h3><p>본문<\/p>/);
});
test('every v3 release appears once with detailed content in descending order',()=>{
 const html=ctx.renderChangelog(markdown);
 const versions=[...markdown.matchAll(/^### (v3\.(\d+))\b/gm)];
 assert.ok(versions.length>=122);
 for(const [,version] of versions){
  const rows=html.match(new RegExp(`<details class="cl-item"><summary>${version.replace('.','\\.')}\\b[\\s\\S]*?</details>`,'g'))||[];
  assert.equal(rows.length,1,version);
  assert.match(rows[0],/<div class="cl-body"><ul><li>/,version);
 }
 for(let i=1;i<versions.length;i++) assert.ok(Number(versions[i-1][2])>Number(versions[i][2]));
 assert.equal((markdown.match(/^# /gm)||[]).length,1);
 assert.doesNotMatch(markdown,/^## v\d/m);
});
test('legacy level-two release titles preserve their detail',()=>{
 const html=ctx.renderChangelog('## v3.121 (2026-10-07)\n- 첫 변경\n## v3.120 (2026-10-07)\n- 둘째 변경\n## 2026-10-06\n### v3.119 — 이전\n- 이전 변경');
 assert.equal((html.match(/<details class="cl-item">/g)||[]).length,3);
 assert.match(html,/v3\.121[^]*?첫 변경[^]*?<\/details>/);
 assert.match(html,/<div class="cl-date">2026-10-06<\/div>/);
});
test('developer note and visible version track latest documented release',()=>{
 const latest=markdown.match(/^### (v\d+\.\d+)/m)[1];
 const dev=fs.readFileSync('DEVNOTE.md','utf8');
 const build=markdown.match(/^### v\d+\.\d+ · (\d{6})/m)[1];
 assert.ok(dev.includes(`현재 기준: **${latest} · build ${build}`));
 assert.ok(fs.readFileSync('templates/index.html','utf8').includes(latest));
 for(const phrase of ['영상 탐색과 재생','서비스 런처·기획서·설치','공통 공유','AI 크레딧과 기부 안내','이벤터스','상단 공통 배너와 상태 반복 조회는 제거']) assert.ok(dev.includes(phrase),phrase);
});
