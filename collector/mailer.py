"""Transactional mail transport for HScope. No credentials in source control."""
import base64
import json
import os
import re
import urllib.error
import urllib.request
import urllib.parse
from email.message import EmailMessage
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
    provider = os.getenv("MAIL_PROVIDER", "resend").strip().lower()
    credentials = (all(os.getenv(k, "").strip() for k in
                       ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"))
                   if provider == "gmail" else bool(os.getenv("RESEND_API_KEY")))
    return {
        "provider": provider,
        "configured": bool(provider in ("gmail", "resend") and credentials and os.getenv("MAIL_FROM") and dest),
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
    provider = os.getenv("MAIL_PROVIDER", "resend").strip().lower()
    if provider == "gmail":
        return _send_gmail_test()
    if provider != "resend":
        raise ValueError("MAIL_PROVIDER는 gmail 또는 resend로 설정하세요.")
    return _send_resend_test()


def _gmail_request(url, data, headers, stage):
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError("invalid response")
        return result
    except urllib.error.HTTPError as exc:
        # Google error bodies may contain credentials. Never expose or log them.
        status_code = exc.code
        exc.close()
        hints = {
            "oauth": "Gmail 연결 인증을 갱신할 수 없습니다. OAuth 클라이언트와 refresh token을 확인하거나 다시 연결하세요.",
            "send": "Gmail 발송이 거부되었습니다. Gmail API 활성화, gmail.send 권한, 발신 계정과 발송 한도를 확인하세요.",
        }
        raise MailProviderError(status_code, "gmail_" + stage + "_error", hints[stage]) from None
    except (ValueError, UnicodeError):
        raise RuntimeError("Gmail 응답을 확인할 수 없습니다. 발송 기록을 확인한 후 다시 시도하세요.") from None


def _send_gmail_test():
    sender = os.getenv("MAIL_FROM", "").strip()
    dest = recipients()
    names = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")
    if not all(os.getenv(k, "").strip() for k in names) or not sender or not dest:
        raise ValueError("Gmail 연결 설정이 필요합니다: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, MAIL_FROM, MAIL_RECIPIENTS")
    if not _EMAIL.fullmatch(sender) or any(not _EMAIL.fullmatch(x) for x in dest):
        raise ValueError("발신 또는 수신 이메일 형식이 올바르지 않습니다.")
    if len(dest) > 5:
        raise ValueError("테스트 수신자는 최대 5명까지 지정할 수 있습니다.")
    token_data = urllib.parse.urlencode({
        "client_id": os.environ["GMAIL_CLIENT_ID"].strip(),
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["GMAIL_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token",
    }).encode()
    token = _gmail_request("https://oauth2.googleapis.com/token", token_data,
                          {"Content-Type": "application/x-www-form-urlencoded"}, "oauth")
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Gmail 연결 인증을 갱신할 수 없습니다. 계정을 다시 연결하세요.")
    subject, plaintext, html = render_test()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(dest)
    message["Subject"] = subject
    message.set_content(plaintext)
    message.add_alternative(html, subtype="html")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    # Address the selected mailbox explicitly: a token for another user must fail.
    url = "https://gmail.googleapis.com/gmail/v1/users/" + urllib.parse.quote(sender, safe="") + "/messages/send"
    result = _gmail_request(url, json.dumps({"raw": raw}).encode(),
                           {"Content-Type": "application/json", "Authorization": "Bearer " + access_token}, "send")
    if not isinstance(result.get("id"), str) or not result["id"]:
        raise RuntimeError("Gmail 발송 접수를 확인할 수 없습니다. 보낸편지함을 확인한 후 다시 시도하세요.")
    return {"accepted": True, "provider_id": result["id"], "recipient_count": len(dest)}


def _send_resend_test():
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
