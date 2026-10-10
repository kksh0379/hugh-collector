"""Persist provider usage without storing prompts, responses or credentials."""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from . import db

KST = timezone(timedelta(hours=9))
# USD / million tokens; verified against Claude pricing on 2026-10-10.
RATES = {'claude-haiku-4-5': (1, 5), 'claude-3-5-haiku': (.8, 4),
         'claude-sonnet-4-6': (3, 15), 'claude-sonnet-4-5': (3, 15), 'claude-sonnet-4': (3, 15), 'claude-3-5-sonnet': (3, 15),
         'claude-3-7-sonnet': (3, 15), 'claude-sonnet-5': (2, 10),
         'claude-opus-4-5': (5, 25), 'claude-opus-4-6': (5, 25),
         'claude-opus-4-7': (5, 25), 'claude-opus-4-8': (5, 25),
         'claude-opus-4-1': (15, 75), 'claude-opus-4': (15, 75)}

def estimate(model, usage, body):
    rates = next((v for k, v in sorted(RATES.items(), key=lambda p: -len(p[0]))
                  if model == k or model.startswith(k + '-')), None)
    if not rates or not isinstance(usage, dict) or 'input_tokens' not in usage or 'output_tokens' not in usage:
        return None
    # Do not pretend to price tiers/tools whose fees aren't supported here.
    if body.get('service_tier') == 'priority' or body.get('speed') == 'fast' or usage.get('server_tool_use'):
        return None
    def n(key):
        return Decimal(str(usage.get(key, 0) or 0))
    inp, out = map(lambda x: Decimal(str(x)), rates)
    context_tokens = n('input_tokens') + n('cache_creation_input_tokens') + n('cache_read_input_tokens')
    if context_tokens > 200000 and not model.startswith(('claude-sonnet-4-6', 'claude-sonnet-5', 'claude-opus-4-6', 'claude-opus-4-7', 'claude-opus-4-8')):
        return None
    cache = usage.get('cache_creation') or {}
    one_hour = Decimal(str(cache.get('ephemeral_1h_input_tokens', 0) or 0))
    five_min = n('cache_creation_input_tokens') - one_hour
    cost = inp * (n('input_tokens') + max(five_min, 0) * Decimal('1.25') + one_hour * 2 + n('cache_read_input_tokens') * Decimal('.1')) + out * n('output_tokens')
    if body.get('inference_geo') == 'us':
        cost *= Decimal('1.1')
    return int(cost.quantize(Decimal('1'), rounding=ROUND_HALF_UP))  # micro USD

def record(response, feature, body, elapsed_ms):
    try:
        payload = response.json()
        if not isinstance(payload, dict):
            payload = {}
        usage = payload.get('usage') or {}
        model = str(payload.get('model') or body.get('model') or '')[:100]
        success = 200 <= response.status_code < 300
        cost = estimate(model, usage, body) if success else None
        tokens = {k: int(usage.get(k, 0) or 0) for k in ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')}
        with db.get_conn() as conn:
            conn.execute(db._q('INSERT INTO ai_usage (id, created_at, feature, model, status, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens, cost_micro, elapsed_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'),
                (uuid.uuid4().hex, datetime.now(KST).isoformat(), str(feature)[:100], model,
                 int(response.status_code), *tokens.values(), cost, elapsed_ms))
    except Exception:
        logging.getLogger(__name__).warning('AI usage record could not be saved', exc_info=False)

def _totals(conn):
    return dict(conn.execute('SELECT COUNT(*) AS requests, COALESCE(SUM(cost_micro),0) AS cost_micro, COALESCE(SUM(input_tokens + output_tokens + cache_write_tokens + cache_read_tokens),0) AS tokens, COALESCE(SUM(CASE WHEN status < 300 AND cost_micro IS NULL THEN 1 ELSE 0 END),0) AS unpriced FROM ai_usage').fetchone())

def dashboard():
    with db.get_conn() as conn:
        total = _totals(conn)
        rows = [dict(r) for r in conn.execute('SELECT * FROM ai_usage ORDER BY created_at DESC, id DESC LIMIT 100').fetchall()]
        saved = conn.execute(db._q('SELECT value FROM meta WHERE key = ?'), ('ai_balance_baseline',)).fetchone()
        baseline = json.loads(saved['value']) if saved else None
    remaining = None
    if baseline and total['unpriced'] == baseline['unpriced']:
        remaining = baseline['balance_micro'] - (total['cost_micro'] - baseline['cost_micro'])
    today = datetime.now(KST).date().isoformat()
    with db.get_conn() as conn:
        daily = dict(conn.execute(db._q('SELECT COUNT(*) AS requests, COALESCE(SUM(cost_micro),0) AS cost_micro FROM ai_usage WHERE created_at >= ?'), (today,)).fetchone())
    return {'totals': total, 'today': daily, 'rows': rows, 'baseline': baseline,
            'remaining_micro': remaining, 'billing_url': 'https://platform.claude.com/settings/billing'}

def set_balance(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 1000000:
            raise ValueError()
        micro = int((amount * 1000000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('잔액은 0~1,000,000달러 사이 숫자로 입력해 주세요.')
    with db.get_conn() as conn:
        total = _totals(conn)
        baseline = {'balance_micro': micro, 'cost_micro': total['cost_micro'], 'unpriced': total['unpriced'], 'updated_at': datetime.now(KST).isoformat()}
        conn.execute(db._q('INSERT INTO meta (key,value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value = excluded.value'), ('ai_balance_baseline', json.dumps(baseline)))
    return baseline
