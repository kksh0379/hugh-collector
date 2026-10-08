"use strict";
(() => {
  const field = document.getElementById('mobile-install-url');
  const status = document.getElementById('mobile-install-status');
  document.getElementById('mobile-install-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(field.value); status.textContent = '휴스코프 주소를 복사했어요.'; }
    catch (_) { field.focus(); field.select(); status.textContent = '주소를 길게 눌러 복사한 뒤 Safari 주소창에 붙여넣어 주세요.'; }
  });
})();
