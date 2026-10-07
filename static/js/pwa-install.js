"use strict";
(() => {
  const launcherUrl = 'https://hscope.onrender.com/hscope';
  const officialOrigin = new URL(launcherUrl).origin;
  const officialHost = window.location.origin === officialOrigin;
  if (officialHost && 'serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {});
  const button = document.getElementById('app-install');
  const dialog = document.getElementById('install-guide');
  if (!button || !dialog) return;
  const status = document.getElementById('install-status');
  const steps = document.getElementById('install-steps');
  const address = document.getElementById('install-address');
  const media = window.matchMedia('(display-mode: standalone)');
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  let feedback = '';
  let deferred = window.HscopeInstallState?.prompt || null;
  let installed = media.matches || navigator.standalone === true || window.HscopeInstallState?.installed === true;
  const nativeBrowser = !ios && /Chrome|Chromium|Edg/i.test(navigator.userAgent);
  function update() {
    button.disabled = installed;
    button.textContent = installed ? '앱으로 실행 중' : ios ? '홈 화면에 추가' : '앱 설치';
    document.getElementById('install-description').textContent = installed
      ? '설치한 아이콘으로 휴스코프를 바로 열 수 있어요.'
      : feedback || '바탕화면이나 홈 화면에 아이콘을 추가해 앱처럼 실행하세요.';
  }
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); if (officialHost) deferred = event; feedback = ''; update(); if (dialog.open && nativeBrowser) dialog.close(); });
  window.addEventListener('appinstalled', () => { installed = true; deferred = null; button.textContent = '설치 완료'; button.disabled = true; if (dialog.open) dialog.close(); });
  media.addEventListener?.('change', event => { installed = event.matches; update(); });
  function guide() {
    let instructions;
    if (ios) instructions = ['Safari에서 아래 휴스코프 주소를 열어주세요.', 'Safari의 공유 버튼을 누르고 ‘홈 화면에 추가’를 선택하세요.', '‘웹 앱으로 열기’ 옵션이 보이면 켜고 ‘추가’를 누르세요.'];
    else if (/Android/i.test(navigator.userAgent)) instructions = ['Chrome에서 아래 휴스코프 주소를 열어주세요.', '브라우저 메뉴(⋮)에서 ‘앱 설치’ 또는 ‘홈 화면에 추가’를 선택하세요.', '설치 안내를 완료하면 홈 화면에 휴스코프 아이콘이 생겨요.'];
    else if (/Mac/i.test(navigator.platform) && /Safari/i.test(navigator.userAgent) && !/Chrome|Chromium|Edg/i.test(navigator.userAgent)) instructions = ['Safari에서 아래 휴스코프 주소를 열어주세요.', '공유 버튼 또는 파일 메뉴에서 ‘Dock에 추가’를 선택하세요.', '이름을 확인하고 ‘추가’를 누르세요.'];
    else instructions = ['Edge 또는 Chrome에서 아래 휴스코프 주소를 열어주세요.', '주소창의 설치 아이콘 또는 브라우저 메뉴의 앱 설치 항목을 선택하세요.', '설치 후 바탕화면·시작 메뉴·작업표시줄에서 실행할 수 있어요.'];
    steps.replaceChildren();
    for (const instruction of instructions) { const item = document.createElement('li'); item.textContent = instruction; steps.append(item); }
    address.value = launcherUrl;
    status.textContent = '설치한 아이콘을 누르면 휴스코프가 바로 열려요.';
    dialog.showModal();
  }
  button.addEventListener('click', async () => {
    if (!officialHost) { window.location.assign(launcherUrl); return; }
    if (installed) return;
    if (!deferred) {
      if (nativeBrowser) {
        feedback = '설치창을 아직 준비하지 못했어요. 잠시 후 앱 설치를 다시 눌러주세요.'; update();
      } else guide();
      return;
    }
    const prompt = deferred; deferred = null;
    if (window.HscopeInstallState) window.HscopeInstallState.prompt = null;
    button.disabled = true;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === 'accepted') { installed = true; button.textContent = '설치 완료'; }
    } catch (_) {
      if (nativeBrowser) feedback = '설치창을 열지 못했어요. 페이지를 새로고침하고 다시 눌러주세요.';
      else guide();
    }
    finally { if (!installed) update(); }
  });
  dialog.querySelector('[data-install-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => button.focus());
  document.getElementById('install-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(address.value); status.textContent = '휴스코프 주소를 복사했어요. 브라우저 주소창에 붙여넣어 주세요.'; }
    catch (_) { address.focus(); address.select(); status.textContent = '아래 주소를 길게 눌러 복사해 주세요.'; }
  });
  document.getElementById('install-help')?.addEventListener('click', guide);
  update();
})();
