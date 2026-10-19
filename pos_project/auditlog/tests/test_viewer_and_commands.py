"""Viewer permissions/filters, review flow, replay and purge commands."""
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditlog import store
from auditlog.api import audit, log_exception
from auditlog.constants import Action, Code, Kind
from auditlog.models import AuditLog, ErrorLog
from users.models import Users


class ViewerTests(TestCase):
    def setUp(self):
        store._down_until = 0.0
        self.cashier = Users.objects.create_user(username='c1', password='x', role=Users.ROLE_CASHIER)
        self.manager = Users.objects.create_user(username='m1', password='x', role=Users.ROLE_MANAGER)
        audit(Action.VOID_ITEM, transaction_no='T9')
        log_exception(Kind.DATA, Code.PRICE_MISSING, 'no price', entity_id='X1')

    def test_cashier_is_blocked_manager_allowed(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(reverse('auditlog:audit_list')).status_code, 302)
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse('auditlog:audit_list')), 'VOID_ITEM')
        self.assertContains(self.client.get(reverse('auditlog:error_list')), 'PRICE_MISSING')

    def test_filter_and_csv(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse('auditlog:audit_list'), {'action': 'LOGOUT'})
        self.assertNotContains(resp, 'VOID_ITEM</td>')
        resp = self.client.get(reverse('auditlog:error_list'), {'csv': 1})
        self.assertEqual(resp['Content-Type'], 'text/csv')

    def test_review_flow(self):
        self.client.force_login(self.manager)
        row = ErrorLog.objects.get()
        self.client.post(reverse('auditlog:error_review', args=[row.pk]),
                         {'status': 'RESOLVED', 'note': 'fixed price'})
        row.refresh_from_db()
        self.assertEqual((row.status, row.note, row.resolved_by), ('RESOLVED', 'fixed price', self.manager))


class CommandTests(TestCase):
    def setUp(self):
        store._down_until = 0.0

    def test_replay_imports_queued_rows(self):
        with tempfile.TemporaryDirectory() as d, override_settings(LOGS_DIR=Path(d)):
            with mock.patch('auditlog.models.AuditLog.objects.create', side_effect=RuntimeError('down')):
                audit(Action.CASH_IN, amount=5)
            store._down_until = 0.0
            self.assertEqual(AuditLog.objects.count(), 0)
            out = StringIO()
            call_command('replay_pending_logs', stdout=out)
            self.assertEqual(AuditLog.objects.get().action, 'CASH_IN')
            self.assertFalse((Path(d) / 'pending_db_logs.jsonl').exists())

    def test_purge_keeps_recent_rows(self):
        audit(Action.LOGOUT)
        audit(Action.LOGIN_OK)
        AuditLog.objects.filter(action='LOGOUT').update(created_at=timezone.now() - timedelta(days=800))
        call_command('purge_logs', stdout=StringIO())
        self.assertEqual(list(AuditLog.objects.values_list('action', flat=True)), ['LOGIN_OK'])


class ConnectionEndpointTests(TestCase):
    def setUp(self):
        store._down_until = 0.0
        self.user = Users.objects.create_user(username='c2', password='x')

    def test_health_ok_without_login(self):
        self.assertEqual(self.client.get(reverse('auditlog:health')).json(), {'ok': True})

    def test_health_503_when_db_fails(self):
        with mock.patch('auditlog.views.connection.cursor', side_effect=RuntimeError('down')):
            self.assertEqual(self.client.get(reverse('auditlog:health')).status_code, 503)

    def test_transaction_status_not_found(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('auditlog:transaction_status', args=['00000042']))
        self.assertEqual(resp.json()['status'], 'not_found')

    def test_client_event_records_audit_and_rejects_unknown(self):
        self.client.force_login(self.user)
        url = reverse('auditlog:client_event')
        ok = self.client.post(url, {'event': 'CONNECTION_LOST', 'trans_no': 'T1'}, content_type='application/json')
        bad = self.client.post(url, {'event': 'LOGIN_OK'}, content_type='application/json')
        self.assertEqual((ok.status_code, bad.status_code), (200, 400))
        self.assertEqual(AuditLog.objects.get().action, 'CONNECTION_LOST')
