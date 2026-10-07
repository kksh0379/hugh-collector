"use strict";

(() => {
  const dialog = document.getElementById('share-dialog');
  if (!dialog) return;
  const title = document.getElementById('share-item-title');
  const urlField = document.getElementById('share-url');
  const status = document.getElementById('share-status');
  const buttons = dialog.querySelectorAll('[data-share-action]');
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const sms = document.getElementById('share-sms');
  let payload = null, trigger = null, busy = false;

  function close() { dialog.close(); }
  dialog.querySelector('[data-share-close]').addEventListener('click', close);
  dialog.addEventListener('close', () => { trigger?.focus(); });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
  });

  function open(url, label, button) {
    let parsed;
    try { parsed = new URL(url); } catch (_) { return; }
    if (!['https:', 'http:'].includes(parsed.protocol) || parsed.username || parsed.password) return;
    payload = {url: parsed.href, title: String(label || '휴스코프에서 공유한 링크').trim().slice(0, 200)};
    trigger = button;
    title.textContent = payload.title;
    urlField.value = payload.url;
    status.textContent = typeof navigator.share === 'function'
      ? '카카오톡은 휴대폰 공유 목록에서 선택해 주세요.'
      : '이 브라우저에서는 앱 공유가 지원되지 않아요. URL을 복사해 원하는 앱에 붙여넣어 주세요.';
    sms.querySelector('small').textContent = ios ? '공유 목록에서 메시지 선택' : '메시지 작성 화면 열기';
    busy = false;
    buttons.forEach(button => { button.disabled = false; });
    if (!dialog.open) dialog.showModal();
  }

  async function nativeShare(target) {
    if (typeof navigator.share !== 'function') {
      status.textContent = '앱 공유를 지원하지 않는 브라우저예요. 아래 URL 복사를 이용해 주세요.';
      return;
    }
    status.textContent = target === 'kakao' ? '공유 목록에서 카카오톡을 선택해 주세요.'
      : target === 'sms' ? '공유 목록에서 메시지를 선택해 주세요.' : '공유할 앱을 선택해 주세요.';
    try {
      await navigator.share({title: payload.title, text: payload.title, url: payload.url});
      close();
    } catch (error) {
      if (error.name !== 'AbortError') status.textContent = '공유창을 열지 못했어요. URL 복사를 이용하거나 휴대폰 브라우저에서 다시 시도해 주세요.';
    }
  }

  buttons.forEach(button => button.addEventListener('click', async () => {
    if (!payload || busy) return;
    busy = true;
    buttons.forEach(item => { item.disabled = true; });
    try {
      const action = button.dataset.shareAction;
      if (action === 'copy') {
        const ok = await copyToClipboard(payload.url);
        status.textContent = ok ? 'URL을 복사했어요.' : '복사하지 못했어요. 아래 주소를 길게 눌러 복사해 주세요.';
        if (!ok) { urlField.focus(); urlField.select(); }
      } else if (action === 'sms' && !ios) {
        const body = encodeURIComponent(payload.title + '\n' + payload.url);
        window.location.href = 'sms:?body=' + body;
        status.textContent = '메시지 작성 화면에서 받는 사람을 선택해 주세요.';
      } else {
        await nativeShare(action);
      }
    } finally {
      busy = false;
      buttons.forEach(item => { item.disabled = false; });
    }
  }));
  window.HscopeShare = {open};
})();
