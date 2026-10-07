"use strict";
(() => {
  const button = document.getElementById('app-install');
  const dialog = document.getElementById('install-guide');
  if (!button || !dialog) return;
  const status = document.getElementById('install-status');
  const steps = document.getElementById('install-steps');
  const address = document.getElementById('install-address');
  const media = window.matchMedia('(display-mode: standalone)');
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  let deferred = null;
  let installed = media.matches || navigator.standalone === true;
  function update() {
    button.disabled = installed;
    button.textContent = installed ? '앱으로 실행 중' : ios ? '홈 화면에 추가' : '앱 설치';
    document.getElementById('install-description').textContent = installed
      ? '서비스 아이콘으로 런처를 열고 원하는 서비스를 선택할 수 있어요.'
      : '바탕화면이나 홈 화면에 아이콘을 추가해 앱처럼 실행하세요.';
  }
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); deferred = event; update(); });
  window.addEventListener('appinstalled', () => { installed = true; deferred = null; button.textContent = '설치 완료'; button.disabled = true; if (dialog.open) dialog.close(); });
  media.addEventListener?.('change', event => { installed = event.matches; update(); });
  function guide() {
    let instructions;
    if (ios) instructions = ['Safari에서 아래 런처 주소를 열어주세요.', 'Safari의 공유 버튼을 누르고 ‘홈 화면에 추가’를 선택하세요.', '‘웹 앱으로 열기’ 옵션이 보이면 켜고 ‘추가’를 누르세요.'];
    else if (/Android/i.test(navigator.userAgent)) instructions = ['Chrome에서 아래 런처 주소를 열어주세요.', '브라우저 메뉴(⋮)에서 ‘앱 설치’ 또는 ‘홈 화면에 추가’를 선택하세요.', '설치 안내를 완료하면 홈 화면에 서비스 홈 아이콘이 생겨요.'];
    else if (/Mac/i.test(navigator.platform) && /Safari/i.test(navigator.userAgent) && !/Chrome|Chromium|Edg/i.test(navigator.userAgent)) instructions = ['Safari에서 아래 런처 주소를 열어주세요.', '공유 버튼 또는 파일 메뉴에서 ‘Dock에 추가’를 선택하세요.', '이름을 확인하고 ‘추가’를 누르세요.'];
    else instructions = ['Edge 또는 Chrome에서 아래 런처 주소를 열어주세요.', '주소창의 설치 아이콘 또는 브라우저 메뉴의 앱 설치 항목을 선택하세요.', '설치 후 바탕화면·시작 메뉴·작업표시줄에서 실행할 수 있어요.'];
    steps.replaceChildren();
    for (const instruction of instructions) { const item = document.createElement('li'); item.textContent = instruction; steps.append(item); }
    address.value = window.location.origin + '/';
    status.textContent = '설치한 아이콘을 누르면 서비스 런처가 먼저 열려요.';
    dialog.showModal();
  }
  button.addEventListener('click', async () => {
    if (installed) return;
    if (!deferred) { guide(); return; }
    const prompt = deferred; deferred = null; button.disabled = true;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === 'accepted') { installed = true; button.textContent = '설치 완료'; }
    } catch (_) { guide(); }
    finally { if (!installed) update(); }
  });
  dialog.querySelector('[data-install-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => button.focus());
  document.getElementById('install-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(address.value); status.textContent = '런처 주소를 복사했어요. 브라우저 주소창에 붙여넣어 주세요.'; }
    catch (_) { address.focus(); address.select(); status.textContent = '아래 주소를 길게 눌러 복사해 주세요.'; }
  });
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {});
  update();
})();
