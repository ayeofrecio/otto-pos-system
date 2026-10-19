"""
The only place that writes AuditLog / ErrorLog rows.

Guarantees:
  * never raises (a logging failure must not break a sale);
  * a DB write runs in its own savepoint, so a failure cannot poison the
    caller's open transaction;
  * if the DB write fails, the row is appended to a local JSONL file
    (replayed later by `manage.py replay_pending_logs`) and DB writes are
    skipped for `breaker_seconds` so requests don't wait on a dead server.
"""
import hashlib
import json
import logging
import re
import threading
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import conf

log = logging.getLogger('auditlog')
_file_lock = threading.Lock()
_down_until = 0.0   # monotonic time until which we skip the DB

_CARD_RE = re.compile(r'\b\d{13,19}\b')


# --- helpers ---------------------------------------------------------------

def _mask_card(match):
    s = match.group(0)
    return '*' * (len(s) - 4) + s[-4:]


def redact_text(text):
    """Mask anything that looks like a card number."""
    return _CARD_RE.sub(_mask_card, text) if isinstance(text, str) else text


def redact(value):
    """Return a JSON-safe copy of `value` with sensitive keys/numbers masked."""
    keys = conf.get('redact_keys')
    if isinstance(value, dict):
        return {str(k): ('***' if str(k).lower() in keys else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(v) for v in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(str(value))


def make_fingerprint(kind, code, logger_name, message, where=''):
    raw = f'{kind}|{code}|{logger_name}|{message[:200]}|{where}'
    return hashlib.sha1(raw.encode('utf-8', 'replace')).hexdigest()


def _write_fallback(model_name, fields):
    try:
        path = Path(settings.LOGS_DIR) / conf.get('fallback_file')
        line = json.dumps({'model': model_name, 'fields': fields}, default=str)
        with _file_lock, open(path, 'a', encoding='utf-8') as fh:
            fh.write(line + '\n')
    except Exception:
        log.exception('Could not write pending log line')


def _db_available():
    return time.monotonic() >= _down_until


def _trip_breaker():
    global _down_until
    _down_until = time.monotonic() + conf.get('breaker_seconds')


# --- public writers --------------------------------------------------------

def save_audit(**fields):
    """Insert an AuditLog row (or queue it in the fallback file)."""
    if not conf.get('enabled'):
        return
    fields.setdefault('created_at', timezone.now().isoformat())
    if _db_available():
        try:
            from .models import AuditLog
            with transaction.atomic():
                AuditLog.objects.create(**{**fields, 'created_at': timezone.now()})
            return
        except Exception:
            _trip_breaker()
            log.warning('AuditLog DB write failed; queued to file', exc_info=True)
    _write_fallback('audit', fields)


def save_error(**fields):
    """Insert an ErrorLog row, or bump `count` on a recent identical one."""
    if not conf.get('enabled'):
        return
    fields.setdefault('created_at', timezone.now().isoformat())
    if _db_available():
        try:
            from .models import ErrorLog
            now = timezone.now()
            window = now - timedelta(seconds=conf.get('dedup_window_seconds'))
            with transaction.atomic():
                bumped = ErrorLog.objects.filter(
                    fingerprint=fields['fingerprint'], last_seen__gte=window,
                ).exclude(status='RESOLVED').update(count=F('count') + 1, last_seen=now)
                if not bumped:
                    ErrorLog.objects.create(**{**fields, 'created_at': now, 'last_seen': now})
            return
        except Exception:
            _trip_breaker()
            log.warning('ErrorLog DB write failed; queued to file', exc_info=True)
    _write_fallback('error', fields)
