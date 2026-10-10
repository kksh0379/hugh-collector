"use strict";
// Render only when a feature reports an actual credit shortage. No network calls.
(() => {
  const account = '9003-3068-2476-1';
  function openDonation(event, url) {
    // Direct user gesture; popup blocking keeps the ordinary safe link usable.
    try {
      const popup = window.open(url, 'hscope-donation',
        'popup=yes,width=480,height=760,resizable=yes,scrollbars=yes');
      if (popup) { popup.opener = null; event.preventDefault(); }
    } catch (_) { /* Keep the link fallback. */ }
  }
  function isCreditNotice(text) {
    return String(text || '').includes('AI 크레딧이 부족');
  }
  function render(target, text) {
    target.replaceChildren();
    target.dataset.aiCredit = 'true';
    const parts = String(text || '').split(account);
    parts.forEach((part, index) => {
      if (index) {
        // WebKit's native data detectors can underline text through a shadow
        // link that CSS cannot reach. Input values are not detected as links.
        const number = document.createElement('input');
        number.className = 'ai-credit-account';
        number.type = 'text';
        number.value = account;
        number.readOnly = true;
        number.size = account.length;
        number.autocomplete = 'off';
        number.spellcheck = false;
        number.setAttribute('aria-label', '새마을금고 후원 계좌번호');
        target.append(number);
      }
      target.append(document.createTextNode(part));
    });
    const actions = document.createElement('span');
    actions.className = 'ai-credit-actions';
    const donation = document.createElement('a');
    donation.className = 'ai-credit-donation';
    donation.href = 'https://aq.gy/f/C4DRg';
    donation.target = '_blank';
    donation.rel = 'noopener noreferrer';
    donation.textContent = '후원하기';
    donation.addEventListener('click', event => openDonation(event, donation.href));
    actions.append(donation);
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
  const header = document.getElementById('header-donation');
  if (header) header.addEventListener('click', event => openDonation(event, header.href));
})();
