from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


class Users(AbstractUser):
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

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)
    middle_initial = models.CharField(max_length=1, blank=True, default='')
    suffix = models.CharField(max_length=6, blank=True, default='')
    store_id = models.CharField(max_length=3, blank=True, default='001')
    terminal_id = models.CharField(max_length=3, blank=True, default='001')
    is_suspended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_user"

    def __str__(self):
        return f"{self.get_full_name() or self.username} [{self.get_role_display()}]"

    @property
    def is_cashier(self):
        return self.role == self.ROLE_CASHIER

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN


class POSSession(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    # Who started the session — immutable audit record
    opened_by = models.ForeignKey(
        Users,
        on_delete=models.PROTECT,
        related_name="opened_sessions"
    )

    # Who actually closed it — any member of the session, set on close
    closed_by = models.ForeignKey(
        Users,
        on_delete=models.PROTECT,
        related_name="closed_sessions",
        null=True,
        blank=True
    )

    terminal_id = models.CharField(max_length=10)
    store_id = models.CharField(max_length=10, default='001')
    business_date = models.DateField()

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    opening_cash = models.DecimalField(max_digits=10, decimal_places=2)
    closing_cash = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    class Meta:
        db_table = "pos_session"
        indexes = [
            models.Index(fields=["terminal_id"]),
            models.Index(fields=["store_id", "business_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Session {self.id} — {self.opened_by} ({self.terminal_id})"

    def add_user(self, user):
        """Add a user to this session. Safe to call if already a member."""
        POSSessionUsers.objects.get_or_create(session=self, user=user)

    def close(self, closed_by_user, closing_cash=None):
        """
        Close the session. Raises ValidationError if the user is not
        an active member of this session.
        """
        from django.utils import timezone

        if self.status != self.STATUS_OPEN:
            raise ValidationError(f"Session is already {self.status}.")

        is_member = self.session_users.filter(
            user=closed_by_user,
            left_at__isnull=True   # still active in the session
        ).exists()

        if not is_member:
            raise ValidationError(
                f"{closed_by_user} is not an active member of this session."
            )

        self.closed_by = closed_by_user
        self.closed_at = timezone.now()
        self.closing_cash = closing_cash
        self.status = self.STATUS_CLOSED
        self.save(update_fields=["closed_by", "closed_at", "closing_cash", "status"])

        # Mark all active session users as left
        self.session_users.filter(left_at__isnull=True).update(left_at=self.closed_at)


class POSSessionUsers(models.Model):
    """
    Bridge table: which users are (or were) part of a session.
    Any active member (left_at=None) can close the session.
    """

    session = models.ForeignKey(
        POSSession,
        on_delete=models.CASCADE,
        related_name="session_users"
    )

    user = models.ForeignKey(
        Users,
        on_delete=models.PROTECT,
        related_name="user_sessions"
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pos_session_users"
        unique_together = ("session", "user")
        indexes = [
            models.Index(fields=["session", "left_at"]),
        ]

    def __str__(self):
        status = "active" if self.left_at is None else f"left {self.left_at:%Y-%m-%d %H:%M}"
        return f"Session {self.session_id} — {self.user.username} ({status})"