from django.contrib import admin

from .models import AuditLog, ErrorLog


class _ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(_ReadOnlyAdmin):
    list_display = ('created_at', 'action', 'success', 'username', 'terminal', 'transaction_no')
    list_filter = ('action', 'success', 'terminal')
    search_fields = ('username', 'transaction_no')


@admin.register(ErrorLog)
class ErrorLogAdmin(_ReadOnlyAdmin):
    list_display = ('last_seen', 'kind', 'code', 'count', 'status', 'message')
    list_filter = ('kind', 'code', 'status')
    search_fields = ('message', 'entity_id', 'transaction_no')
