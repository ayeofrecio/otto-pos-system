"""
Public API - the only module call sites need.

    from auditlog.api import audit, log_exception, get_logger
    from auditlog.constants import Action, Kind, Code

    audit(Action.PRICE_OVERRIDE, transaction_no=no, approver=mgr.username,
          line=2, old=499, new=399)
    log_exception(Kind.DATA, Code.ITEM_NOT_FOUND, 'Barcode not found',
                  entity='barcode', entity_id=barcode)
    logger = get_logger('payment')      # normal text logging -> logs/app.log

Both functions never raise and need no try/except at the call site.
"""
import logging
import traceback as tb

from .store import make_fingerprint, redact, redact_text, save_audit, save_error
from .middleware import get_context

_text_log = logging.getLogger('pos.exceptions')


def get_logger(area):
    return logging.getLogger(f'pos.{area}')


def audit(action, *, transaction_no='', approver='', success=True,
          username=None, session_id=None, **details):
    """Record a business event. Extra keyword args go into `details`."""
    try:
        ctx = get_context()
        save_audit(
            action=str(action),
            success=success,
            user_id=ctx.get('user_id'),
            username=username if username is not None else ctx.get('username', ''),
            approver_username=approver or '',
            terminal=ctx.get('terminal', ''),
            session_id=session_id,
            transaction_no=str(transaction_no or ''),
            request_id=ctx.get('request_id', ''),
            ip=ctx.get('ip'),
            path=ctx.get('path', ''),
            details=redact(details),
        )
    except Exception:
        logging.getLogger('auditlog').exception('audit() failed')


def log_exception(kind, code, message, *, entity='', entity_id='',
                  exc=None, level='WARNING', transaction_no='', **context):
    """
    Record a problem in the exception table. Use for handled data/device
    problems (no Python exception needed); pass `exc=e` to include a traceback.
    """
    try:
        ctx = get_context()
        message = redact_text(str(message))[:2000]
        trace = ''
        where = ''
        if exc is not None:
            trace = ''.join(tb.format_exception(type(exc), exc, exc.__traceback__))[-20000:]
            frames = tb.extract_tb(exc.__traceback__)
            if frames:
                where = f'{frames[-1].filename}:{frames[-1].name}'
        _text_log.warning('[%s/%s] %s', kind, code, message)
        save_error(
            fingerprint=make_fingerprint(str(kind), str(code), 'pos.exceptions',
                                         f'{message}{entity_id}', where),
            kind=str(kind), code=str(code), level=level,
            logger='pos.exceptions', message=message, traceback=redact_text(trace),
            entity=str(entity)[:40], entity_id=str(entity_id)[:60],
            context=redact(context),
            user_id=ctx.get('user_id'), username=ctx.get('username', ''),
            terminal=ctx.get('terminal', ''), transaction_no=str(transaction_no or ''),
            request_id=ctx.get('request_id', ''), path=ctx.get('path', ''),
            method=ctx.get('method', ''),
        )
    except Exception:
        logging.getLogger('auditlog').exception('log_exception() failed')
