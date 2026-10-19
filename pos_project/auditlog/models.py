"""
AuditLog  - business events (who did what, when).
ErrorLog  - the exception table: crashes AND data problems (see constants.Kind).

Rows are append-only. The only permitted update is a manager's review of an
ErrorLog row (status / resolved_by / resolved_at / note).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from .constants import Status


class _ContextFields(models.Model):
    """Who/where fields shared by both tables."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    username = models.CharField(max_length=150, blank=True, default='')  # survives user deletion
    terminal = models.CharField(max_length=20, blank=True, default='')
    transaction_no = models.CharField(max_length=30, blank=True, default='')
    request_id = models.CharField(max_length=36, blank=True, default='')
    path = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        abstract = True


class AuditLog(_ContextFields):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    action = models.CharField(max_length=40)          # values: constants.Action
    success = models.BooleanField(default=True)
    approver_username = models.CharField(max_length=150, blank=True, default='')
    session_id = models.BigIntegerField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['terminal', 'created_at']),
            models.Index(fields=['transaction_no']),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('AuditLog rows are append-only.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} {self.username}'


class ErrorLog(_ContextFields):
    REVIEW_FIELDS = {'status', 'resolved_by', 'resolved_at', 'note'}

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now)
    count = models.PositiveIntegerField(default=1)
    fingerprint = models.CharField(max_length=40, db_index=True)
    kind = models.CharField(max_length=12)            # values: constants.Kind
    code = models.CharField(max_length=40)            # values: constants.Code
    level = models.CharField(max_length=10, default='ERROR')
    logger = models.CharField(max_length=80, blank=True, default='')
    message = models.TextField(blank=True, default='')
    traceback = models.TextField(blank=True, default='')
    entity = models.CharField(max_length=40, blank=True, default='')      # e.g. 'barcode'
    entity_id = models.CharField(max_length=60, blank=True, default='')   # e.g. '4800123456789'
    context = models.JSONField(default=dict, blank=True)
    method = models.CharField(max_length=8, blank=True, default='')
    status = models.CharField(max_length=10, default=Status.NEW, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-last_seen', '-id']
        indexes = [
            models.Index(fields=['kind', 'status', 'last_seen']),
            models.Index(fields=['fingerprint', 'last_seen']),
            models.Index(fields=['transaction_no']),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            fields = kwargs.get('update_fields')
            if not fields or set(fields) - self.REVIEW_FIELDS:
                raise ValueError('ErrorLog rows are append-only; only review fields can change.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.kind}/{self.code} x{self.count}'
