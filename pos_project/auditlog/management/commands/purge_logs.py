"""Delete old log rows. Schedule daily, e.g.: manage.py purge_logs"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auditlog import conf
from auditlog.models import AuditLog, ErrorLog


class Command(BaseCommand):
    help = 'Delete AuditLog / ErrorLog rows older than the retention settings.'

    def add_arguments(self, parser):
        parser.add_argument('--audit-days', type=int, default=conf.get('audit_retention_days'))
        parser.add_argument('--error-days', type=int, default=conf.get('error_retention_days'))

    def handle(self, *args, **opts):
        now = timezone.now()
        a, _ = AuditLog.objects.filter(created_at__lt=now - timedelta(days=opts['audit_days'])).delete()
        e, _ = ErrorLog.objects.filter(last_seen__lt=now - timedelta(days=opts['error_days'])).delete()
        self.stdout.write(f'Deleted {a} audit rows, {e} exception rows.')
