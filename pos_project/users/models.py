# users_app/models.py

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    One-to-one extension of Django's auth_user table.
    Stores POS-specific details. Django session auth is unchanged.
    """

    ROLE_CASHIER    = 'cashier'
    ROLE_SUPERVISOR = 'supervisor'
    ROLE_MANAGER    = 'manager'
    ROLE_ADMIN      = 'admin'

    ROLE_CHOICES = [
        (ROLE_CASHIER,    'Cashier'),
        (ROLE_SUPERVISOR, 'Supervisor'),
        (ROLE_MANAGER,    'Manager'),
        (ROLE_ADMIN,      'Admin'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role           = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)
    middle_initial = models.CharField(max_length=1, blank=True, default='')
    suffix         = models.CharField(max_length=6, blank=True, default='')
    store_id       = models.CharField(max_length=3, blank=True, default='001')
    terminal_id    = models.CharField(max_length=3, blank=True, default='001')
    is_suspended   = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profile'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} [{self.get_role_display()}]'

    @property
    def is_cashier(self):
        return self.role == self.ROLE_CASHIER

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN


