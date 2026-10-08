(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const dialog=$('healthcheck-dialog'); if(!dialog) return;
  const labels={passed:'정상',warning:'주의',failed:'확인 필요',skipped:'미점검',running:'실행 중',interrupted:'중단',service_failure:'서비스 점검 실패',test_failure:'테스트 검증 실패',test_error:'테스트 실행 예외',test_environment:'테스트 환경 오류',probe_error:'점검 도구 오류',needs_review:'점검 결과 확인 필요'};
  const rowCategory=row=>row.category||(row.status==='failed'?(String(row.group).includes('회귀 테스트')?'test_failure':'service_failure'):row.status);
  let selected='',timer=null,report=null,busy=false;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const duration=ms=>{ms=Math.max(0,Number(ms)||0);if(ms<1000)return Math.round(ms)+'ms';if(ms<60000)return (ms/1000).toFixed(1)+'초';return Math.floor(ms/60000)+'분 '+Math.floor(ms%60000/1000)+'초';};
  const stamp=value=>value?new Date(value).toLocaleString('ko-KR',{hour12:false,timeZone:'Asia/Seoul'}):'—';
  async function request(url,options={}){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
    try{const response=await fetch(url,{cache:'no-store',...options,signal:controller.signal});const data=await response.json();if(!response.ok)throw Error(data.error||'점검 결과를 불러오지 못했어요.');return data;}
    finally{clearTimeout(timeout);}
  }
  function render(){
    const host=$('healthcheck-results');
    if(!report){host.innerHTML='<p class="hc-empty">아직 점검 기록이 없어요. 지금 점검을 실행할 수 있어요.</p>';$('healthcheck-summary').textContent='매일 새벽 3시 · 한국 시간';$('healthcheck-timing').innerHTML='';$('healthcheck-progress').hidden=true;$('healthcheck-run').disabled=busy;return;}
    const rows=report.results||[],keys=['passed','service_failure','test_failure','test_error','test_environment','probe_error','warning','skipped'],counts=Object.fromEntries(keys.map(k=>[k,rows.filter(r=>rowCategory(r)===k).length]));
    const elapsed=report.status==='running'?Date.now()-Date.parse(report.started_at):report.duration_ms;
    const assessment=report.assessment_status||report.status;
    $('healthcheck-summary').innerHTML=`<span class="hc-badge ${esc(assessment)}">${esc(labels[assessment]||assessment)}</span><span>${keys.map(k=>`${labels[k]} ${counts[k]}`).join(' · ')}</span>`;
    $('healthcheck-timing').innerHTML=`<div><span>시작</span><strong>${esc(stamp(report.started_at))}</strong></div><div><span>종료</span><strong>${esc(stamp(report.finished_at))}</strong></div><div><span>${report.status==='running'?'경과 시간':'총 소요 시간'}</span><strong id="healthcheck-elapsed">${duration(elapsed)}</strong></div>`;
    $('healthcheck-progress').hidden=report.status!=='running';
    $('healthcheck-progress').textContent=`${report.phase||'점검 중'} · ${rows.length}/${report.total||'?'} 항목 완료`;
    $('healthcheck-run').disabled=busy||report.status==='running';
    const open=new Set(Array.from(host.querySelectorAll('details[open]')).map(el=>el.dataset.group));
    const filtered=$('healthcheck-problems').checked?rows.filter(row=>row.status!=='passed'):rows;
    const groups=new Map();for(const row of filtered){if(!groups.has(row.group))groups.set(row.group,[]);groups.get(row.group).push(row);}
    host.innerHTML=Array.from(groups,([group,items])=>`<details class="hc-group" data-group="${esc(group)}"${open.has(group)?' open':''}><summary><strong>${esc(group)}</strong><span>${items.length}건 · ${duration(items.reduce((sum,r)=>sum+(r.duration_ms||0),0))}</span></summary><ul>${items.map(row=>`<li><div class="hc-row-head"><span class="hc-badge ${esc(rowCategory(row))}">${esc(labels[rowCategory(row)]||rowCategory(row))}</span><strong>${esc(row.name)}</strong><time>${duration(row.duration_ms)}</time></div><p>${esc(row.detail)}</p>${row.assessment_note?`<p>${esc(row.assessment_note)}</p>`:''}</li>`).join('')}</ul></details>`).join('')||'<p class="hc-empty">표시할 점검 결과가 없어요.</p>';
  }
  async function load(){
    try{
      const data=await request('/api/admin/healthchecks'+(selected?'?id='+encodeURIComponent(selected):''));
      report=data.report;
      const history=$('healthcheck-history');
      history.innerHTML='<option value="">최근 실행</option>'+(data.history||[]).map(row=>`<option value="${esc(row.id)}">${esc(stamp(row.started_at))} · ${esc(labels[row.assessment_status||row.status]||row.status)} · ${duration(row.duration_ms)} · ${row.trigger==='scheduled'?'자동':row.trigger==='verification'?'배포 확인':'수동'}</option>`).join('');history.value=selected;
      $('healthcheck-error').textContent='';render();
    }catch(e){$('healthcheck-error').textContent=e.name==='AbortError'?'조회가 지연되고 있어요. 다시 시도해 주세요.':e.message;}
    finally{clearTimeout(timer);if(dialog.open&&report?.status==='running')timer=setTimeout(load,3000);}
  }
  $('healthchecks-btn').addEventListener('click',()=>{selected='';dialog.showModal();load();});
  $('healthcheck-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>clearTimeout(timer));
  $('healthcheck-history').addEventListener('change',event=>{selected=event.target.value;load();});
  $('healthcheck-refresh').addEventListener('click',load);
  $('healthcheck-problems').addEventListener('change',render);
  $('healthcheck-run').addEventListener('click',async()=>{
    if(busy)return;busy=true;$('healthcheck-run').disabled=true;
    try{const data=await request('/api/admin/healthchecks/run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});selected=data.id;await load();}
    catch(e){$('healthcheck-error').textContent=e.message;}
    finally{busy=false;$('healthcheck-run').disabled=report?.status==='running';}
  });
  setInterval(()=>{if(dialog.open&&report?.status==='running'){const el=$('healthcheck-elapsed');if(el)el.textContent=duration(Date.now()-Date.parse(report.started_at));}},1000);
  new MutationObserver(()=>{if(!document.body.classList.contains('is-admin')&&dialog.open)dialog.close();}).observe(document.body,{attributes:true,attributeFilter:['class']});
})();
