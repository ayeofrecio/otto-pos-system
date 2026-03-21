from django.db import models
from django.contrib.auth.models import AbstractUser


class Users(AbstractUser):
    """
    Custom User model extending Django's authentication system.
    Stores POS-specific details.
    """

    ROLE_CASHIER = 'cashier'
    ROLE_SUPERVISOR = 'supervisor'
    ROLE_MANAGER = 'manager'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_CASHIER, 'Cashier'),
        (ROLE_SUPERVISOR, 'Supervisor'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_ADMIN, 'Admin'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_CASHIER
    )

    middle_initial = models.CharField(
        max_length=1,
        blank=True,
        default=''
    )

    suffix = models.CharField(
        max_length=6,
        blank=True,
        default=''
    )

    store_id = models.CharField(
        max_length=3,
        blank=True,
        default='001'
    )

    terminal_id = models.CharField(
        max_length=3,
        blank=True,
        default='001'
    )

    is_suspended = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} [{self.get_role_display()}]"

    @property
    def is_cashier(self):
        return self.role == self.ROLE_CASHIER

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN


class POSSession(models.Model):
    """
    POS terminal session tracking.
    """

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    cashier = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    terminal_id = models.CharField(max_length=10)
    store_id = models.CharField(max_length=10, default='001')
    business_date = models.DateField()

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    opening_cash = models.DecimalField(max_digits=10, decimal_places=2)

    closing_cash = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN
    )

    class Meta:
        db_table = "pos_session"
        indexes = [
            models.Index(fields=["terminal_id"]),
        ]

    def __str__(self):
        return f"Session {self.id} - {self.cashier} ({self.terminal_id})"