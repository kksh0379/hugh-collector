"use strict";
(() => {
  const modal = document.getElementById('accounts-modal');
  if (!modal) return;
  const form = document.getElementById('account-form');
  const list = document.getElementById('accounts-list');
  const status = document.getElementById('accounts-status');
  const username = document.getElementById('account-username');
  const name = document.getElementById('account-name');
  const password = document.getElementById('account-password');
  let editing = null, busy = false;
  const say = (text, error=false) => { status.textContent=text; status.classList.toggle('account-error',error); };
  function reset() { editing=null; form.reset(); form.hidden=true; }
  function close() { if(busy)return; reset(); modal.hidden=true; document.body.classList.remove('modal-open'); document.getElementById('accounts-btn').focus(); }
  function edit(row) {
    if(busy || row?.locked)return;
    form.reset(); editing=row?.username || null;
    username.value=editing || ''; username.readOnly=!!editing;
    name.value=row?.display_name || ''; password.required=!editing;
    document.getElementById('account-form-title').textContent=editing?'일반 계정 수정':'일반 계정 추가';
    document.getElementById('account-password-help').textContent=editing?'변경할 때만 8~128자로 입력하세요. 비워두면 기존 비밀번호를 유지해요.':'8~128자로 입력해 주세요.';
    form.hidden=false; (editing?name:username).focus();
  }
  async function api(path, options={}) {
    const response=await fetch('/api/admin/accounts'+path,{cache:'no-store',...options});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error || '요청을 완료하지 못했어요.');
    return data;
  }
  async function load() {
    const {accounts}=await api('');
    list.replaceChildren();
    accounts.forEach(row=>{
      const card=document.createElement('div'); card.className='account-row';
      const info=document.createElement('div'); info.className='account-info';
      const title=document.createElement('strong'); title.textContent=row.display_name;
      const detail=document.createElement('small'); detail.textContent=row.username+' · '+(row.locked?'관리자 · 변경 불가':'일반 계정');
      info.append(title,detail);
      const actions=document.createElement('div'); actions.className='account-actions';
      const modify=document.createElement('button'); modify.type='button'; modify.className='btn-status'; modify.textContent='수정'; modify.disabled=row.locked; modify.onclick=()=>edit(row);
      const remove=document.createElement('button'); remove.type='button'; remove.className='btn-status account-delete'; remove.textContent='삭제'; remove.disabled=row.locked;
      if(row.locked) { modify.title=remove.title='관리자 계정은 이 기능에서 변경할 수 없어요.'; }
      else remove.onclick=()=>{
        if(busy)return;
        say(row.username+' 계정을 삭제하면 로그인할 수 없고 기존 개인 자료는 보존돼요. 삭제를 확정하려면 한 번 더 눌러 주세요.');
        armConfirm(remove,'삭제 확정',()=>run(async()=>{await api('/'+encodeURIComponent(row.username),{method:'DELETE'});reset();await load();say('계정을 삭제했어요. 기존 로그인도 더 이상 사용할 수 없어요.');}));
      };
      actions.append(modify,remove);card.append(info,actions);list.append(card);
    });
  }
  async function run(action) {
    if(busy)return;
    busy=true;
    const controls=[...modal.querySelectorAll('button,input')].filter(e=>!e.disabled);
    controls.forEach(e=>e.disabled=true);
    try { await action(); }
    catch(error) { say(error.message,true); }
    finally { controls.forEach(e=>e.disabled=false); busy=false; }
  }
  document.getElementById('accounts-btn').onclick=()=>{
    reset(); list.replaceChildren(); modal.hidden=false; document.body.classList.add('modal-open');
    document.getElementById('accounts-close').focus(); say('계정 목록을 불러오는 중…');
    run(async()=>{await load();say('관리자 계정은 보호돼요. 일반 계정을 선택해 관리하세요.');});
  };
  document.getElementById('accounts-close').onclick=close;
  modal.addEventListener('click',e=>{if(e.target===modal)close();});
  modal.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}});
  document.getElementById('account-add').onclick=()=>edit(null);
  document.getElementById('account-cancel').onclick=reset;
  document.getElementById('accounts-refresh').onclick=()=>run(async()=>{await load();say('목록을 새로 불러왔어요.');});
  form.onsubmit=e=>{
    e.preventDefault(); if(busy)return;
    const payload={username:username.value.trim().toLowerCase(),display_name:name.value.trim(),password:password.value};
    const target=editing; say('저장 중…');
    run(async()=>{
      await api(target?'/'+encodeURIComponent(target):'',{method:target?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      reset();await load();say(target?'계정을 수정했어요. 해당 사용자는 다시 로그인해야 해요.':'일반 계정을 추가했어요. 로그인에서 다른 계정을 선택해 사용할 수 있어요.');
    });
  };
})();
