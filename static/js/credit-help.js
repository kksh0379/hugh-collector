"use strict";
// Render only when a feature reports an actual credit shortage. No network calls.
(() => {
  const account = '9003-3068-2476-1';
  function isCreditNotice(text) {
    return String(text || '').includes('AI 크레딧이 부족');
  }
  function render(target, text) {
    target.replaceChildren();
    target.dataset.aiCredit = 'true';
    const parts = String(text || '').split(account);
    parts.forEach((part, index) => {
      if (index) {
        const number = document.createElement('span');
        number.className = 'ai-credit-account';
        number.textContent = account;
        target.append(number);
      }
      target.append(document.createTextNode(part));
    });
    const actions = document.createElement('span');
    actions.className = 'ai-credit-actions';
    const link = document.createElement('a');
    link.className = 'ai-credit-billing';
    link.href = 'https://platform.claude.com/settings/billing';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = '크레딧 결제 · 운영자용';
    actions.append(link);
    target.append(actions);
  }
  window.HScopeCreditHelp = {render, isCreditNotice};
})();
