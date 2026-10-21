(() => {
  const button = document.getElementById('mail-test-btn');
  if (!button) return;
  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    const label = button.textContent;
    button.textContent = '메일 연결 확인 중…';
    try {
      const statusRes = await fetch('/api/admin/mail/status', {credentials:'same-origin'});
      const status = await statusRes.json();
      if (!statusRes.ok) throw new Error(status.error || '관리자 인증이 필요합니다.');
      if (!status.configured) throw new Error('발송 설정이 필요합니다. Render 환경변수 RESEND_API_KEY, MAIL_FROM, MAIL_RECIPIENTS를 먼저 설정하세요.');
      if (!confirm('등록된 수신자 ' + status.recipient_count + '명에게 테스트 메일을 발송할까요?')) return;
      button.textContent = '발송 중…';
      const res = await fetch('/api/admin/mail/test', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'},body:'{}'});
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '발송에 실패했습니다.');
      alert('메일 공급자 접수 완료. 실제 받은편지함과 스팸함에서 수신 여부를 확인하세요.');
    } catch (error) {
      alert(error.message || '메일 테스트에 실패했습니다.');
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  });
})();
