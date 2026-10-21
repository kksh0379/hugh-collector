"""Transactional mail transport for HScope. No credentials in source control."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import escape

_EMAIL = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")

# Only known codes and locally authored summaries may leave this module.
# Provider messages can echo addresses, credentials, or arbitrary HTML.
_ERROR_HINTS = {
    "validation_error": "Resend 요청 검증에 실패했습니다. 발신 도메인과 수신자 조건을 확인하세요.",
    "missing_api_key": "Resend API 키가 누락되었습니다.",
    "restricted_api_key": "Resend API 키의 활성 상태, 발송 권한 및 허용 도메인을 확인하세요.",
    "invalid_permission": "Resend API 키의 발송 권한 및 허용 도메인을 확인하세요.",
    "suspended_api_key": "Resend API 키가 정지되었습니다. Resend에서 상태를 확인하세요.",
    "rate_limit_exceeded": "Resend 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.",
    "daily_quota_exceeded": "Resend 일일 발송 한도를 초과했습니다.",
    "monthly_quota_exceeded": "Resend 월간 발송 한도를 초과했습니다.",
    "application_error": "Resend 내부 오류입니다. 잠시 후 다시 시도하세요.",
    "service_unavailable": "Resend 서비스를 일시적으로 사용할 수 없습니다.",
}


class MailProviderError(RuntimeError):
    """Safe for administrator responses and logs; never contains raw bodies."""

    def __init__(self, http_status, provider_code, hint):
        self.http_status = http_status
        self.provider_code = provider_code
        super().__init__(f"메일 공급자 요청 실패 (HTTP {http_status}, {provider_code}): {hint}")


def _provider_error(exc):
    code, hint = "unknown_error", "Resend 상세 오류를 확인할 수 없습니다. 관리자에게 문의하세요."
    try:
        raw = exc.read(8193)
        payload = json.loads(raw) if len(raw) <= 8192 else None
        if isinstance(payload, dict):
            name, message = payload.get("name"), payload.get("message")
            if isinstance(name, str) and name in _ERROR_HINTS:
                code, hint = name, _ERROR_HINTS[name]
                if name == "validation_error" and isinstance(message, str):
                    message = message.lower()
                    if "only send testing emails to your own email address" in message:
                        hint = ("onboarding@resend.dev 테스트 발신은 Resend 계정 이메일로만 보낼 수 있습니다. "
                                "현재 수신자가 계정 이메일과 같은지 확인하세요. 다른 수신자에게 보내려면 "
                                "Resend에서 소유 도메인을 인증하고 해당 도메인의 MAIL_FROM을 설정하세요.")
                    elif "domain is not verified" in message.replace("`", ""):
                        hint = "MAIL_FROM의 도메인이 Resend에서 인증되지 않았습니다. 도메인 인증 상태를 확인하세요."
                    elif "api key is invalid" in message:
                        hint = "Resend API 키가 유효하지 않습니다. 키의 활성 상태와 Render 등록값을 확인하세요."
    except (OSError, ValueError, UnicodeError):
        pass
    finally:
        exc.close()
    return MailProviderError(exc.code, code, hint)


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
        "test_sender": os.getenv("MAIL_FROM", "").strip().lower() == "onboarding@resend.dev",
        "sender_notice": ("Resend 테스트 발신 주소는 Resend 계정 이메일로만 발송할 수 있습니다. "
                          "다른 수신자는 인증된 소유 도메인의 발신 주소가 필요합니다.")
                         if os.getenv("MAIL_FROM", "").strip().lower() == "onboarding@resend.dev" else "",
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
        raise _provider_error(exc) from None
