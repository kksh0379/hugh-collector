"""Server-side password gate for the private Maeum plan and its static files."""
import hmac
import os
import posixpath
import secrets

from flask import make_response, redirect, render_template, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

ACCESS_COOKIE = "maeum_access"
FORM_COOKIE = "maeum_form"
ACCESS_SECONDS = 1800


def register_maeum_gate(app):
    # An independent random signing key also protects deployments using the
    # legacy Flask SECRET_KEY default. All threads in this worker share it.
    signer = URLSafeTimedSerializer(os.environ.get("MAEUM_GATE_SECRET") or secrets.token_hex(32),
                                   salt="maeum-record-access-v1")

    def authorized():
        try:
            return signer.loads(request.cookies.get(ACCESS_COOKIE, ""),
                                max_age=ACCESS_SECONDS) == "maeum-record"
        except BadSignature:
            return False

    def prompt(error=None, status=200):
        challenge = signer.dumps(secrets.token_urlsafe(24))
        response = make_response(render_template("maeum_password.html", error=error,
                                                  challenge=challenge), status)
        response.set_cookie(FORM_COOKIE, challenge, max_age=600, httponly=True,
                            secure=request.is_secure, samesite="Lax", path="/maeum-record")
        return response

    @app.before_request
    def protect_maeum():
        path = posixpath.normpath(request.path)
        page = path == "/maeum-record"
        asset = path.startswith("/static/plans/maeum-record")
        if not (page or asset):
            return None
        if authorized():
            return None
        if asset:
            return make_response("비밀번호 확인 후 열 수 있습니다.", 403)
        if request.method == "POST":
            challenge = request.form.get("challenge", "")
            try:
                valid_form = bool(challenge) and hmac.compare_digest(
                    challenge, request.cookies.get(FORM_COOKIE, ""))
                signer.loads(challenge, max_age=600)
            except BadSignature:
                valid_form = False
            if not valid_form:
                return prompt("확인 화면이 만료됐어요. 다시 입력해 주세요.", 400)
            password = os.environ.get("MAEUM_RECORD_PASSWORD", "1234")
            if not hmac.compare_digest(request.form.get("password", "").encode(), password.encode()):
                return prompt("비밀번호가 올바르지 않습니다.", 401)
            response = redirect("/maeum-record", code=303)
            response.set_cookie(ACCESS_COOKIE, signer.dumps("maeum-record"),
                                max_age=ACCESS_SECONDS, httponly=True, secure=request.is_secure,
                                samesite="Lax", path="/")
            response.delete_cookie(FORM_COOKIE, path="/maeum-record")
            return response
        return prompt()

    @app.after_request
    def prevent_maeum_caching(response):
        path = posixpath.normpath(request.path)
        if path == "/maeum-record" or path.startswith("/static/plans/maeum-record"):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Referrer-Policy"] = "same-origin"
        return response
