"""Transactional mail transport for HScope. No credentials in source control."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import escape

_EMAIL = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


def recipients():
    raw = os.getenv("MAIL_RECIPIENTS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def status():
    dest = recipients()
    return {
        "provider": "resend",
        "configured": bool(os.getenv("RESEND_API_KEY") and os.getenv("MAIL_FROM") and dest),
        "sender_configured": bool(os.getenv("MAIL_FROM")),
        "recipient_count": len(dest),
        "enabled_daily": os.getenv("MAIL_DAILY_ENABLED", "").lower() == "true",
    }


def render_test():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = "휴스코프 메일 발송 테스트"
    body = "발신·수신 연결이 정상적으로 설정되었는지 확인하는 테스트 메일입니다."
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"></head>
    <body style="margin:0;background:#f4f6fa;font-family:Arial,sans-serif;color:#202a3e">
    <div style="max-width:580px;margin:32px auto;padding:28px;background:#fff;border-radius:18px">
    <p style="font-size:12px;color:#2864b4;font-weight:700">HSCOPE · MAIL TEST</p>
    <h1 style="font-size:24px">{escape(title)}</h1><p style="line-height:1.8">{escape(body)}</p>
    <p style="font-size:12px;color:#667085">발송 시각: {escape(now)}</p>
    <hr style="border:0;border-top:1px solid #e5e7eb"><p style="font-size:12px;color:#667085">
    이 메일은 관리자가 수동으로 요청한 연결 테스트입니다.</p></div></body></html>"""
    return title, body + "\n발송 시각: " + now, html


def send_test():
    api_key = os.getenv("RESEND_API_KEY", "")
    sender = os.getenv("MAIL_FROM", "").strip()
    dest = recipients()
    if not api_key or not sender or not dest:
        raise ValueError("RESEND_API_KEY, MAIL_FROM, MAIL_RECIPIENTS 설정이 필요합니다.")
    if not _EMAIL.fullmatch(sender) or any(not _EMAIL.fullmatch(x) for x in dest):
        raise ValueError("발신 또는 수신 이메일 형식이 올바르지 않습니다.")
    if len(dest) > 5:
        raise ValueError("테스트 수신자는 최대 5명까지 지정할 수 있습니다.")
    subject, plaintext, html = render_test()
    data = json.dumps({"from": sender, "to": dest, "subject": subject,
                       "html": html, "text": plaintext}, ensure_ascii=False).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=data, method="POST",
                                 headers={"Authorization": "Bearer " + api_key,
                                          "Content-Type": "application/json",
                                          "User-Agent": "hscope-mail/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
            return {"accepted": True, "provider_id": result.get("id"), "recipient_count": len(dest)}
    except urllib.error.HTTPError as exc:
        # Never return provider body or credentials; administrator sees only status.
        raise RuntimeError("메일 공급자 요청 실패 (HTTP %s)" % exc.code) from None
