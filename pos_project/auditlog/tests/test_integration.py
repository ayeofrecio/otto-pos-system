"""Smoke tests: instrumented views still work and leave an audit trail."""
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from auditlog.models import AuditLog
from users.models import Users


class LoginAuditTests(TestCase):
    def setUp(self):
        Users.objects.create_user(username='cash1', password='secret123')

    @mock.patch('users.views._get_store_name', return_value='Test Store')
    def test_failed_and_successful_login_are_audited(self, _store):
        url = reverse('pos_login')
        self.client.post(url, {'username': 'cash1', 'password': 'wrong'})
        self.client.post(url, {'username': 'cash1', 'password': 'secret123'})
        self.client.get(reverse('pos_logout'))
        actions = list(AuditLog.objects.order_by('id').values_list('action', 'success', 'username'))
        self.assertEqual(actions, [
            ('LOGIN_FAIL', False, 'cash1'),
            ('LOGIN_OK', True, 'cash1'),
            ('LOGOUT', True, 'cash1'),
        ])
