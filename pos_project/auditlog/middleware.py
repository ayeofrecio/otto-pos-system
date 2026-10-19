"""
Request context for logging.

AuditContextMiddleware remembers the current request in a contextvar so that
audit(), log_exception() and the logging handlers can attach user / terminal /
request id without every call site passing them.

Everything here is defensive: a failure while collecting context must never
break the request.
"""
import contextvars
import logging
import time
import uuid

from . import conf

_current_request = contextvars.ContextVar('auditlog_request', default=None)
_request_id = contextvars.ContextVar('auditlog_request_id', default='')

slow_logger = logging.getLogger('pos.request')


def get_context():
    """Return who/where info for the current request ({} outside a request)."""
    request = _current_request.get()
    ctx = {'request_id': _request_id.get()}
    if request is None:
        return ctx
    try:
        user = getattr(request, 'user', None)
        authed = bool(user is not None and user.is_authenticated)
        session = getattr(request, 'session', {})
        ctx.update(
            user_id=user.pk if authed else None,
            username=user.get_username() if authed else '',
            terminal=session.get('terminal_id') or conf.get('default_terminal'),
            ip=request.META.get('REMOTE_ADDR') or None,
            path=request.path[:200],
            method=request.method,
        )
    except Exception:
        pass  # e.g. session DB unreachable - keep whatever we have
    return ctx


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = uuid.uuid4().hex[:16]
        req_token = _current_request.set(request)
        id_token = _request_id.set(rid)
        started = time.monotonic()
        try:
            response = self.get_response(request)
            try:
                response['X-Request-ID'] = rid
                elapsed = time.monotonic() - started
                if elapsed > conf.get('slow_request_seconds'):
                    slow_logger.warning('Slow request %s %s took %.2fs',
                                        request.method, request.path, elapsed)
            except Exception:
                pass
            return response
        finally:
            _current_request.reset(req_token)
            _request_id.reset(id_token)
