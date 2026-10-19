"""
Manager/admin pages for AuditLog and ErrorLog (read-only, plus review of errors).

  /logs/audit/   business events        (?csv=1 to export)
  /logs/errors/  exception table        (?csv=1 to export, POST to mark reviewed)
"""
import csv
import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from sales.models import TempTransaction, TransactionHeader
from users.decorators import manager_required

from .api import audit

from .constants import Action, Code, Kind, Status
from .models import AuditLog, ErrorLog

PAGE_SIZE = 50


def _filtered(qs, request, exact=(), contains=(), date_field='created_at'):
    """Apply ?field=value filters plus ?date_from / ?date_to (YYYY-MM-DD)."""
    for field in exact:
        value = request.GET.get(field, '').strip()
        if value:
            qs = qs.filter(**{field: value})
    for field in contains:
        value = request.GET.get(field, '').strip()
        if value:
            qs = qs.filter(**{f'{field}__icontains': value})
    if request.GET.get('date_from'):
        qs = qs.filter(**{f'{date_field}__date__gte': request.GET['date_from']})
    if request.GET.get('date_to'):
        qs = qs.filter(**{f'{date_field}__date__lte': request.GET['date_to']})
    return qs


def _csv_response(name, qs, fields):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{name}.csv"'
    writer = csv.writer(response)
    writer.writerow(fields)
    for row in qs.iterator():
        writer.writerow([getattr(row, f) for f in fields])
    return response


def _render_list(request, template, qs, **extra):
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, template, {
        'page': page, 'query': params.urlencode(), 'get': request.GET, **extra,
    })


@manager_required
def audit_list(request):
    qs = _filtered(AuditLog.objects.all(), request,
                   exact=('action', 'terminal'), contains=('username', 'transaction_no'))
    if request.GET.get('csv'):
        return _csv_response('audit_log', qs, [
            'created_at', 'action', 'success', 'username', 'approver_username',
            'terminal', 'transaction_no', 'details'])
    return _render_list(request, 'auditlog/audit_list.html', qs, actions=Action.values)


@manager_required
def error_list(request):
    qs = _filtered(ErrorLog.objects.all(), request, date_field='last_seen',
                   exact=('kind', 'code', 'status'), contains=('username', 'transaction_no'))
    if request.GET.get('csv'):
        return _csv_response('exception_log', qs, [
            'created_at', 'last_seen', 'count', 'kind', 'code', 'status', 'message',
            'entity', 'entity_id', 'username', 'terminal', 'transaction_no'])
    return _render_list(request, 'auditlog/error_list.html', qs,
                        kinds=Kind.values, codes=Code.values, statuses=Status.values)


@manager_required
@require_POST
def error_review(request, pk):
    """Mark an exception NEW / REVIEWED / RESOLVED with an optional note."""
    row = get_object_or_404(ErrorLog, pk=pk)
    status = request.POST.get('status')
    if status in Status.values:
        row.status = status
        row.note = request.POST.get('note', '').strip()
        row.resolved_by = request.user if status == Status.RESOLVED else None
        row.resolved_at = timezone.now() if status == Status.RESOLVED else None
        row.save(update_fields=['status', 'note', 'resolved_by', 'resolved_at'])
    return redirect(request.POST.get('next') or 'auditlog:error_list')


# --- connection-loss support (used by static/sales/connection.js) ----------

def health(request):
    """Heartbeat: 200 if the app AND database answer, else 503."""
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
    except Exception:
        return JsonResponse({'ok': False}, status=503)
    return JsonResponse({'ok': True})


@login_required
def transaction_status(request, trans_no):
    """completed / open / not_found - lets the cashier check a sale after a dropped connection."""
    if TransactionHeader.objects.filter(transaction_no=trans_no, transaction_type='S').exists():
        state = 'completed'
    elif TempTransaction.objects.filter(transaction_no=trans_no).exists():
        state = 'open'
    else:
        state = 'not_found'
    return JsonResponse({'transaction_no': trans_no, 'status': state})


@login_required
@require_POST
def client_event(request):
    """Browser reports a connection drop / recovery (sent once the link is back)."""
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'ok': False}, status=400)
    action = data.get('event')
    if action not in (Action.CONNECTION_LOST, Action.CONNECTION_RESTORED):
        return JsonResponse({'ok': False}, status=400)
    audit(action, transaction_no=str(data.get('trans_no') or '')[:30],
          lost_at=str(data.get('lost_at', ''))[:30],
          restored_at=str(data.get('restored_at', ''))[:30],
          seconds=data.get('seconds'), page=str(data.get('page', ''))[:100])
    return JsonResponse({'ok': True})
