"""
Logging plumbing, wired up in config/logging_config.py:

  DatabaseErrorHandler - stores every ERROR+ log record in ErrorLog (kind SYSTEM)
  ContextFilter        - adds request_id / user / terminal to text log lines
  RedactionFilter      - masks card numbers in log messages
  NoiseFilter          - drops 404s for /favicon.ico
"""
import logging
import threading
import traceback as tb

from .middleware import get_context
from .store import make_fingerprint, redact_text, save_error

_local = threading.local()   # re-entrancy guard
_SKIP_LOGGERS = ('auditlog', 'django.db.backends')


class ContextFilter(logging.Filter):
    def filter(self, record):
        ctx = get_context()
        record.request_id = ctx.get('request_id') or '-'
        record.user = ctx.get('username') or '-'
        record.terminal = ctx.get('terminal') or '-'
        return True


class RedactionFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = redact_text(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


class NoiseFilter(logging.Filter):
    def filter(self, record):
        return 'favicon.ico' not in record.getMessage()


class DatabaseErrorHandler(logging.Handler):
    def __init__(self, level=logging.ERROR):
        super().__init__(level)

    def emit(self, record):
        if record.name.startswith(_SKIP_LOGGERS) or getattr(_local, 'busy', False):
            return
        _local.busy = True
        try:
            trace, where = '', ''
            if record.exc_info and record.exc_info[0]:
                trace = ''.join(tb.format_exception(*record.exc_info))[-20000:]
                frames = tb.extract_tb(record.exc_info[2])
                if frames:
                    where = f'{frames[-1].filename}:{frames[-1].name}'
            message = redact_text(record.getMessage())[:2000]
            ctx = get_context()
            save_error(
                fingerprint=make_fingerprint('SYSTEM', 'UNHANDLED', record.name, message, where),
                kind='SYSTEM', code='UNHANDLED', level=record.levelname,
                logger=record.name[:80], message=message, traceback=redact_text(trace),
                user_id=ctx.get('user_id'), username=ctx.get('username', ''),
                terminal=ctx.get('terminal', ''), request_id=ctx.get('request_id', ''),
                path=ctx.get('path', ''), method=ctx.get('method', ''),
            )
        except Exception:
            pass  # a logging handler must never raise
        finally:
            _local.busy = False
