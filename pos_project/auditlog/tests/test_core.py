"""Contract tests: logging must record correctly and must never break callers."""
import json
import logging
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, RequestFactory, override_settings

from auditlog import store
from auditlog.api import audit, log_exception
from auditlog.constants import Action, Code, Kind
from auditlog.handlers import DatabaseErrorHandler
from auditlog.middleware import AuditContextMiddleware
from auditlog.models import AuditLog, ErrorLog


class _Base(TestCase):
    def setUp(self):
        store._down_until = 0.0


class AuditTests(_Base):
    def test_audit_writes_row_and_redacts(self):
        audit(Action.PRICE_OVERRIDE, transaction_no='T1', approver='mgr',
              old=499, new=399, pin='1234', note='card 4111111111111111')
        row = AuditLog.objects.get()
        self.assertEqual(row.action, 'PRICE_OVERRIDE')
        self.assertEqual(row.approver_username, 'mgr')
        self.assertEqual(row.details['pin'], '***')
        self.assertEqual(row.details['note'], 'card ************1111')

    def test_audit_rows_are_append_only(self):
        audit(Action.LOGOUT)
        row = AuditLog.objects.get()
        with self.assertRaises(ValueError):
            row.save()

    def test_audit_never_raises_and_falls_back_to_file(self):
        with tempfile.TemporaryDirectory() as d, \
                override_settings(LOGS_DIR=Path(d)), \
                mock.patch('auditlog.models.AuditLog.objects.create', side_effect=RuntimeError('db down')):
            audit(Action.CASH_IN, amount=100)          # must not raise
            lines = (Path(d) / 'pending_db_logs.jsonl').read_text().splitlines()
            self.assertEqual(json.loads(lines[0])['model'], 'audit')
            # circuit breaker: next call goes straight to the file
            audit(Action.CASH_OUT, amount=50)
            self.assertEqual(len((Path(d) / 'pending_db_logs.jsonl').read_text().splitlines()), 2)


class ExceptionTests(_Base):
    def test_log_exception_and_dedup(self):
        for _ in range(3):
            log_exception(Kind.DATA, Code.ITEM_NOT_FOUND, 'Barcode not found',
                          entity='barcode', entity_id='123')
        row = ErrorLog.objects.get()
        self.assertEqual((row.kind, row.code, row.count), ('DATA', 'ITEM_NOT_FOUND', 3))
        self.assertEqual(row.status, 'NEW')

    def test_log_exception_captures_traceback(self):
        try:
            1 / 0
        except ZeroDivisionError as e:
            log_exception(Kind.DEVICE, Code.PRINTER_FAIL, 'print failed', exc=e)
        self.assertIn('ZeroDivisionError', ErrorLog.objects.get().traceback)

    def test_review_fields_only(self):
        log_exception(Kind.DATA, Code.PRICE_MISSING, 'x')
        row = ErrorLog.objects.get()
        row.status = 'RESOLVED'
        row.save(update_fields=['status'])
        row.message = 'tampered'
        with self.assertRaises(ValueError):
            row.save(update_fields=['message'])


class HandlerTests(_Base):
    def test_error_records_go_to_errorlog(self):
        logger = logging.getLogger('pos.test_handler')
        handler = DatabaseErrorHandler()
        logger.addHandler(handler)
        logger.propagate = False
        try:
            try:
                raise ValueError('boom')
            except ValueError:
                logger.exception('Receipt failed')
            logger.warning('ignored below ERROR')
        finally:
            logger.removeHandler(handler)
        row = ErrorLog.objects.get()
        self.assertEqual((row.kind, row.code, row.message), ('SYSTEM', 'UNHANDLED', 'Receipt failed'))
        self.assertIn('ValueError: boom', row.traceback)


class MiddlewareTests(_Base):
    def test_sets_request_id_and_context_reaches_audit(self):
        def view(request):
            audit(Action.X_READ)
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = RequestFactory().get('/pos/x')
        response = AuditContextMiddleware(view)(request)
        row = AuditLog.objects.get()
        self.assertTrue(response['X-Request-ID'])
        self.assertEqual(row.request_id, response['X-Request-ID'])
        self.assertEqual(row.path, '/pos/x')
