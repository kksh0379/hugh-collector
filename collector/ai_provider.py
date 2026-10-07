"""Shared credit failure handling for every token-consuming AI request."""
import threading
import time
import requests

NOTICE = ('AI 크레딧이 부족해요.\n기부해 주시면 AI 크레딧을 충전할게요.\n'
          '새마을금고 9003-3068-2476-1\n예금주: 김상화')
BILLING_URL = 'https://platform.claude.com/settings/billing'
_lock = threading.Lock()
_state = {}
_blocked_until = 0


class CreditUnavailable(RuntimeError):
    reason = 'credit_balance'
    curation_reason = 'credit_balance'

    def __init__(self):
        super().__init__(NOTICE)


def is_credit_error(error):
    if isinstance(error, CreditUnavailable):
        return True
    response = getattr(error, 'response', None)
    if response is not None:
        error = response.text
    text = str(error or '').lower()
    return any(term in text for term in ('credit balance', 'purchase credits',
        'insufficient_quota', 'insufficient_credit', 'insufficient credit',
        'insufficient balance', 'billing_hard_limit', '크레딧이 부족'))


def status():
    with _lock:
        return dict(_state)


def post(url, *, feature, **kwargs):
    global _blocked_until
    with _lock:
        if time.monotonic() < _blocked_until:
            raise CreditUnavailable()
    response = requests.post(url, **kwargs)
    if response.status_code >= 400:
        # Inspect the complete provider payload before any caller truncates it.
        if is_credit_error(response.text):
            with _lock:
                _blocked_until = time.monotonic() + 60
                _state.update(reason='credit_balance', notice=NOTICE, feature=feature,
                              billing_url=BILLING_URL, checked_at=time.time())
            raise CreditUnavailable()
    else:
        with _lock:
            _blocked_until = 0
            _state.clear()
    return response
