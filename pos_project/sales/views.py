"""
POS Cashier views: login, cashier screen, cart operations.
"""
import os

import datetime
import django.utils.timezone as timezone
from decimal import Decimal
from io import StringIO
from decimal import Decimal, InvalidOperation
from pyexpat.errors import messages
from django.http import JsonResponse

from django.db import models
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command, CommandError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from users.models import POSSession
from users.models import Users
from users.models import POSSession, POSSessionUsers

from .color_lookup import get_color_description
from .size_lookup import get_size_description
from .decorators import require_open_session
from .models import Item, ItemDetail, TempTransaction, TerminalConfiguration, TerminalReceiptFooter, TransactionHeader, POSTransNumber, Tender, TerminalSetup, Color, Size, Payment, TransactionItem
from .services import get_business_date
from .transaction_services.transaction_service import TransactionService, RecordCode
from .pos_constants import (
    RCODE_ITEM_VOID,
    TAG_ITEM_RETURN,
    TAG_PRICE_OVERRIDE,
    TAG_ITEM_VOID,
    TAG_VOID_PREVIOUS,
    TAG_VOID_TRANS,
    TRTYPE_VOID_ITEM,
    TRTYPE_VOID_ITEM_LEGACY,
    TRTYPE_VOID_PREVIOUS,
    TRTYPE_VOID_TRANS,
    TRTYPE_VOID_TRANS_LEGACY,
    VOID_TRANSACTION_TYPES_ALL,
)

from sales.services import import_products_from_csv
from setup.pos_keys import get_pos_keys


#  for debugging
from pprint import pprint
from django.forms.models import model_to_dict

from django.db.models import Sum, Count, Q
import json
import socket
import time
import serial
# # For printing (Serial type of POS Printer)
# from .print_services import ReceiptPrinter
# from escpos.printer import Serial

# ---------------------------------------------------------------------------
# Session keys and defaults
# ---------------------------------------------------------------------------

STORE_ID = "001"
TERMINAL_ID = "001"



# ---------------------------------------------------------------------------
# Transaction-level discount helpers
# ---------------------------------------------------------------------------

def _get_trans_disc(request):
    """Read transaction discount from session. Returns dict with pct, type, label."""
    try:
        pct = Decimal(str(float(request.session.get("pos_trans_disc_pct", "0") or "0")))
    except (ValueError, TypeError):
        pct = Decimal("0")
    return {
        "pct": pct,
        "type": request.session.get("pos_trans_disc_type", ""),
        "label": request.session.get("pos_trans_disc_label", ""),
    }


def _compute_totals(cart_lines, trans_disc):
    """Return (subtotal, trans_disc_amt, total) given cart lines and trans discount."""
    subtotal = sum(line.item_price_ext or Decimal("0") for line in cart_lines)
    pct = trans_disc.get("pct", Decimal("0"))
    if pct > 0:
        disc_amt = (subtotal * pct / 100).quantize(Decimal("0.0001"))
        total = subtotal - disc_amt
    else:
        disc_amt = Decimal("0")
        total = subtotal
    return subtotal, disc_amt, total


def _clear_trans_disc(request):
    """Remove transaction discount from session."""
    for key in ("pos_trans_disc_pct", "pos_trans_disc_type", "pos_trans_disc_label"):
        request.session.pop(key, None)


def _verify_manager_pin(pin: str):
    """Return manager/admin user object when PIN matches; else None."""
    clean_pin = (pin or "").strip()
    if not clean_pin:
        return None

    managers = Users.objects.filter(
        role__in=[Users.ROLE_MANAGER, Users.ROLE_ADMIN, Users.ROLE_SUPERVISOR],
        is_active=True,
        is_suspended=False,
    )

    for user in managers:
        if user.check_password(clean_pin):
            return user
    return None


def _build_temp_line_cart_context(request, trans_no):
    """Build cart context values used by cart mutation endpoints."""
    user_id = _get_user_id(request)
    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)
    return {
        "cart_lines": cart_lines,
        "subtotal": subtotal,
        "trans_disc": trans_disc,
        "trans_disc_amt": trans_disc_amt,
        "total": total,
        "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
        "last_item": cart_lines.last(),
    }


def _get_user_id(request):
    """Return user_id for POS (Django username or ClarionUser id)."""
    return request.user.username[:10] if request.user.is_authenticated else ""


# ----------------------------------------------------------------------------
# Getting the current session's store_id and terminal_id from the POSSession model instead of the user model allows for more flexible assignment of terminals to users and better tracking of sessions across different terminals. This way, the store_id and terminal_id are tied to the actual POS session rather than the user account, which can be useful in scenarios where users may operate multiple terminals or when terminals are shared among users. The helper functions can be updated to retrieve this information from the current open session for the logged-in user, ensuring that all operations are correctly associated with the active session's store and terminal.
# ----------------------------------------------------------------------------
def get_current_session(request):
    if not request.user.is_authenticated:
        return None

    return (
        POSSession.objects.filter(
            session_users__user=request.user,
            session_users__left_at__isnull=True,
            status=POSSession.STATUS_OPEN,
        )
        .order_by("-opened_at")
        .first()
    )

def get_current_session_or_error(request):
    """Return current session or raise API error response."""
    session = get_current_session(request)

    if not session:
        raise Exception("No active POS session found for this user.")

    return session

def validate_session_owner(request, session):
    """Ensure session belongs to the logged-in user."""
    if not request.user.is_authenticated:
        raise Exception("User not authenticated.")

    if session.cashier != request.user:
        raise Exception("Unauthorized: Session does not belong to this user.")

    return True

def get_session_by_id(request, session_id):
    """Fetch session safely and ensure ownership."""
    try:
        session = POSSession.objects.select_related("opened_by").get(
            id=session_id
        )
    except POSSession.DoesNotExist:
        raise Exception("Session not found.")

    validate_session_owner(request, session)

    return session

# ---------------------------------------------------------------------------
# Store and terminal info helpers
# ---------------------------------------------------------------------------
def _get_store_name():
    """Return store name from TerminalSetup, or default."""
    try:
        setup = TerminalSetup.objects.get(store_id=STORE_ID, terminal_id=TERMINAL_ID)
        return setup.header01 or "POS Store"
    except TerminalSetup.DoesNotExist:
        return "POS Store"

def _get_store_details():
    """Return store details from TerminalSetup, or defaults."""
    try:
        return TerminalSetup.objects.filter(
            store_id=STORE_ID,
            terminal_id=TERMINAL_ID
        ).first()
    except TerminalSetup.DoesNotExist:
        return None


# def _get_terminal_info_from_session(store_id, terminal_id):
#     """Return (terminal_information) from the current open session for this user."""

#     terminal_information = TerminalConfiguration.objects.filter(store_id=store_id, terminal_id=terminal_id).first()
#     return terminal_information
 
def _get_terminal_config():
    """
    Fetch TerminalConfiguration with all relations prefetched.
    Footers are fetched unfiltered — callers filter in Python to avoid
    the fragile to_attr list vs queryset confusion.
    Returns None if not found.
    """
    return (
        TerminalConfiguration.objects
        .prefetch_related("headers", "footers", "ports", "display_codes")
        .filter(store_id=STORE_ID, terminal_id=TERMINAL_ID)
        .first()
    )
 

def _get_terminal_session(store_id, terminal_id):
    """
    Return the currently open session for this terminal+store, or None.
    This is terminal-scoped — independent of which user is logged in.
    """
    return (
        POSSession.objects.filter(
            store_id=store_id,
            terminal_id=terminal_id,
            status=POSSession.STATUS_OPEN,
        )
        .order_by("-opened_at")
        .first()
    )


def _enroll_if_needed(session, user):
    """
    Add the user to the session's member list if not already there.
    Safe to call on every login — get_or_create avoids duplicates.
    """
    obj, created = POSSessionUsers.objects.get_or_create(
        session=session,
        user=user,
        defaults={"left_at": None},
    )
    # If they were previously marked as left (e.g. logged out mid-shift
    # and came back), reactivate them.
    if not created and obj.left_at is not None:
        obj.left_at = None
        obj.save(update_fields=["left_at"])


def _parse_decimal(value, default=Decimal("0")):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return default

# ---------------------------------------------------------------------------

def _normalize_transaction_no(value):
    """Return 8-digit numeric transaction number string."""
    try:
        return str(int(str(value).strip() or "0")).zfill(8)
    except (TypeError, ValueError):
        return "00000000"


def _save_current_transaction_no(trans_no):
    """Persist the latest used transaction number in POSNBR."""
    current_no = _normalize_transaction_no(trans_no)
    row = POSTransNumber.objects.order_by("id").first()
    if row:
        row.transaction_no = current_no
        row.save(update_fields=["transaction_no"])
        return row

    return POSTransNumber.objects.create(transaction_no=current_no)


def _get_next_transaction_no():
    """Get next transaction number from POSNBR and persist it as current."""
    row = POSTransNumber.objects.order_by("id").first()
    if not row:
        # First transaction in a fresh setup.
        return _save_current_transaction_no("00000001").transaction_no

    current = _normalize_transaction_no(row.transaction_no)
    next_no = str(int(current) + 1).zfill(8)
    row.transaction_no = next_no
    row.save(update_fields=["transaction_no"])
    return next_no


@login_required(login_url="pos_login")
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET", "POST"])
def admin_posnbr_init(request):
    """Super-admin tool to initialize/update POSNBR starting transaction number."""
    command_output = ""
    command_error = ""

    if request.method == "POST":
        start = (request.POST.get("start") or "").strip()
        force = bool(request.POST.get("force"))
        out = StringIO()
        try:
            call_command("init_posnbr", start=start, force=force, stdout=out)
            command_output = out.getvalue().strip()
        except CommandError as exc:
            command_error = str(exc)
        except Exception as exc:
            command_error = f"Unexpected error: {exc}"

    posnbr = POSTransNumber.objects.order_by("id").first()
    current_no = _normalize_transaction_no(posnbr.transaction_no) if posnbr else "(not set)"

    return render(
        request,
        "sales/admin_posnbr_init.html",
        {
            "current_no": current_no,
            "command_output": command_output,
            "command_error": command_error,
        },
    )


# Constants
terminal_config = _get_terminal_config()
VAT_RATE = terminal_config.vat if terminal_config and terminal_config.vat else Decimal("0.12")

# ---------------------------------------------------------------------------
# Open session view
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(["GET", "POST"])
def open_session(request):
    user = request.user
    store_id = user.store_id
    terminal_id = user.terminal_id

    existing_session = _get_terminal_session(store_id, terminal_id)

    if existing_session:
        # Terminal already has an open session — just enroll this user in it
        _enroll_if_needed(existing_session, user)
        return redirect("sales:pos_cashier")

    # No open session on this terminal — only the first user creates one
    if request.method == "POST":
        opening_cash = _parse_decimal(request.POST.get("opening_cash"))
        if opening_cash < 0:
            messages.error(request, "Opening cash cannot be negative.")
            return redirect("sales:open_session")

        session = POSSession.objects.create(
            opened_by=user,
            terminal_id=terminal_id,
            store_id=store_id,
            business_date=datetime.date.today(),
            opening_cash=opening_cash,
            status=POSSession.STATUS_OPEN,
        )
        session.add_user(user)

        return redirect("sales:pos_cashier")

    return render(request, "sales/open_session.html")

# ---------------------------------------------------------------------------
# Cashier main view
# ---------------------------------------------------------------------------

@login_required
@require_open_session
def cashier_view(request):
    """Main POS cashier screen."""
    user_id = _get_user_id(request)
    now = datetime.datetime.now()

    try:
        biz_date = get_business_date(STORE_ID, TERMINAL_ID, now)
    except Exception:
        biz_date = now.date()

    # Get or create transaction number for this session's cart
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        trans_no = _get_next_transaction_no()
        request.session["pos_trans_no"] = trans_no

    # Load cart from TempTransaction
    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)
    item_count = sum(int(line.item_qty or 0) for line in cart_lines)

    # Last scanned item for detail panel
    last_line = cart_lines.last()

    context = {
        "store_name": _get_store_name(),
        "date": biz_date.strftime("%A %b %d %Y"),
        "time": now.strftime("%I:%M:%S %p"),
        "cashier": request.user.get_full_name() or request.user.username,
        "receipt_no": trans_no,
        "cart_lines": cart_lines,
        "subtotal": subtotal,
        "trans_disc": trans_disc,
        "trans_disc_amt": trans_disc_amt,
        "total": total,
        "item_count": item_count,
        "last_item": last_line,
        "pos_keys": get_pos_keys(),
        "z_reading_required": getattr(request, "z_reading_required", False),
    }
    return render(request, "sales/cashier.html", context)


# ---------------------------------------------------------------------------
# Cart API (HTMX / JSON)
# ---------------------------------------------------------------------------

@login_required
@require_open_session
@require_http_methods(["GET"])
def item_variants(request):
    """Return color/size variants for an alias item (barcode = icode, len <= 11)."""
    barcode = (request.GET.get("barcode") or "").strip()
    if not barcode:
        return JsonResponse({"ok": False, "error": "Barcode required"}, status=400)

    try:
        item = Item.objects.get(icode=barcode)
    except Item.DoesNotExist:
        return JsonResponse({"ok": False, "is_alias": False, "error": "Item not found"}, status=404)

    if item.is_alias != "Y":
        return JsonResponse({"ok": True, "is_alias": False})

    details = ItemDetail.objects.filter(icode=barcode)
    color_codes = {d.color for d in details if d.color}
    size_codes  = {d.size  for d in details if d.size}

    color_map = {c.code: c.color for c in Color.objects.filter(code__in=color_codes)}
    size_map  = {s.code: s.size  for s in Size.objects.filter(code__in=size_codes)}

    variants = [
        {
            "barcode":    d.barcode,
            "color_code": d.color,
            "color_desc": color_map.get(d.color, d.color),
            "size_code":  d.size,
            "size_desc":  size_map.get(d.size, d.size),
            "price":      float(d.price),
        }
        for d in details
    ]

    return JsonResponse({
        "ok":       True,
        "is_alias": True,
        "item_desc": item.short_desc or item.long_desc or barcode,
        "variants": variants,
    })


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_add(request):
    """Add item by barcode. Returns HTML fragment for HTMX or JSON."""
    barcode = (request.POST.get("barcode") or "").strip()
    if not barcode:
        return JsonResponse({"ok": False, "error": "Barcode required"}, status=400)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        trans_no = _get_next_transaction_no()
        request.session["pos_trans_no"] = trans_no

    now = datetime.datetime.now()
    try:
        biz_date = get_business_date(STORE_ID, TERMINAL_ID, now)
    except Exception:
        biz_date = now.date()

    # Lookup by barcode
    try:
        item_detail = ItemDetail.objects.get(barcode=barcode)
    except ItemDetail.DoesNotExist:
        try:
            item = Item.objects.get(icode=barcode)
            item_detail = None
        except Item.DoesNotExist:
            # 12-char barcode: last 4 digits encode color (2) + size (2)
            if len(barcode) == 12:
                parsed_icode = barcode[:-4]
                parsed_color = barcode[-4:-2].zfill(3)
                parsed_size  = barcode[-2:].zfill(3)
                try:
                    item_detail = ItemDetail.objects.get(
                        icode=parsed_icode,
                        color=parsed_color,
                        size=parsed_size,
                    )
                    item = Item.objects.get(icode=parsed_icode)
                except (ItemDetail.DoesNotExist, Item.DoesNotExist):
                    item_detail = None
                    item = None
                if item_detail and item:
                    # fall through to the item_detail/item assignment block below
                    pass
                else:
                    if request.headers.get("HX-Request"):
                        return render(
                            request,
                            "sales/partials/cart_error.html",
                            {"error": "Item not found"},
                        )
                    return JsonResponse({"ok": False, "error": "Item not found"}, status=404)
            else:
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "sales/partials/cart_error.html",
                        {"error": "Item not found"},
                    )
                return JsonResponse({"ok": False, "error": "Item not found"}, status=404)

    if item_detail:
        item = Item.objects.get(icode=item_detail.icode)
        desc = item.short_desc or item.long_desc or item_detail.icode
        price = item_detail.price or item.price
        size = item_detail.size
        color = item_detail.color
        color_desc = item_detail.color_desc or ""
        item_code = item_detail.icode
    else:
        item = Item.objects.get(icode=barcode)
        desc = item.short_desc or item.long_desc or item.icode
        price = item.price
        size = item.size or ""
        color = item.color or ""
        color_desc = item.color_desc or ""
        item_code = item.icode

    try:
        qty = Decimal(max(1, int(request.POST.get("qty", "1") or "1")))
    except (ValueError, TypeError):
        qty = Decimal("1")

    try:
        disc_pct = Decimal(str(max(0, min(100, float(request.POST.get("disc_pct", "0") or "0")))))
    except (ValueError, TypeError):
        disc_pct = Decimal("0")
    disc_type = (request.POST.get("disc_type") or "").strip()[:3]

    item_discount = (price * disc_pct / 100).quantize(Decimal("0.0001"))
    ext = (price - item_discount) * qty

    max_rec = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).aggregate(mx=models.Max("rec_ctr"))
    rec_ctr = (max_rec["mx"] or 0) + 1

    TempTransaction.objects.create(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        transaction_date=biz_date,
        transaction_time=now.strftime("%H:%M"),
        transaction_type="S",
        item_code=item_code,
        item_description=(desc or "")[:25],
        item_qty=qty,
        item_price=price,
        item_discount=item_discount,
        discount_code=disc_type,
        item_price_ext=ext,
        item_size=size or "",
        item_color=color or "",
        item_color_desc=color_desc or "",
        rec_ctr=rec_ctr,
    )

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)
    last_line = cart_lines.last()

    if request.headers.get("HX-Request"):
        return render(
            request,
            "sales/partials/cart_added.html",
            {
                "cart_lines": cart_lines,
                "subtotal": subtotal,
                "trans_disc": trans_disc,
                "trans_disc_amt": trans_disc_amt,
                "total": total,
                "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
                "last_item": last_line,
            },
        )

    return JsonResponse({
        "ok": True,
        "item_code": item_code,
        "description": desc,
        "price": str(price),
        "total": str(total),
    })


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_remove(request):
    """Remove a cart line by rec_ctr."""
    try:
        rec_ctr = int(request.POST.get("rec_ctr", 0))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid rec_ctr"}, status=400)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        return JsonResponse({"ok": False, "error": "No active transaction"}, status=400)

    deleted, _ = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        rec_ctr=rec_ctr,
    ).delete()

    if not deleted and request.headers.get("HX-Request"):
        return render(request, "sales/partials/cart_error.html", {"error": "Line not found"}, status=404)

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "sales/partials/cart_remove_response.html",
            {
                "cart_lines": cart_lines,
                "subtotal": subtotal,
                "trans_disc": trans_disc,
                "trans_disc_amt": trans_disc_amt,
                "total": total,
                "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
                "last_item": cart_lines.last(),
            },
        )

    return JsonResponse({"ok": True, "total": str(total)})


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_void_item(request):
    """Void one line from the current cart (F8) and classify as item-void."""
    try:
        rec_ctr = int(request.POST.get("rec_ctr", 0))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid rec_ctr"}, status=400)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        return JsonResponse({"ok": False, "error": "No active transaction"}, status=400)

    line = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        rec_ctr=rec_ctr,
    ).first()
    if not line:
        return JsonResponse({"ok": False, "error": "Line not found"}, status=404)

    session = get_current_session(request)
    if not session:
        return JsonResponse({"ok": False, "error": "No open POS session"}, status=400)

    now = datetime.datetime.now()
    header = TransactionHeader.objects.create(
        session=session,
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        transaction_date=session.business_date,
        transaction_time=now.strftime("%H:%M"),
        transaction_type=TRTYPE_VOID_ITEM,
        return_code=RCODE_ITEM_VOID,
        item_ref=str(line.rec_ctr),
    )
    TransactionItem.objects.create(
        header=header,
        item_code=line.item_code or "",
        item_description=line.item_description or "",
        item_qty=line.item_qty or 0,
        item_uom=line.item_uom or "",
        item_supplier=line.item_supplier or "",
        item_department=line.item_department or "",
        item_class=line.item_class or "",
        item_size=line.item_size or "",
        item_color=line.item_color or "",
        item_type=line.item_type or "",
        item_cost=line.item_cost or 0,
        item_price=line.item_price or 0,
        item_discount=line.item_discount or 0,
        discount_code=line.discount_code or "",
        item_price_ext=line.item_price_ext or 0,
        tag1=TAG_ITEM_VOID,
        tag2=line.tag2 or "",
        tag3=line.tag3 or "",
        tag4=line.tag4 or "",
        promo_tag=line.promo_tag or "",
    )

    line.delete()

    context = _build_temp_line_cart_context(request, trans_no)
    if request.headers.get("HX-Request"):
        return render(request, "sales/partials/cart_remove_response.html", context)
    return JsonResponse({
        "ok": True,
        "void_kind": "item",
        "transaction_type": TRTYPE_VOID_ITEM,
        "remaining_items": context["item_count"],
    })


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_void_transaction(request):
    """Void the full active transaction (F7) with manager PIN, same business day."""
    manager_pin = request.POST.get("manager_pin", "")
    manager_user = _verify_manager_pin(manager_pin)
    if not manager_user:
        return JsonResponse({"ok": False, "error": "Manager PIN is invalid"}, status=403)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        return JsonResponse({"ok": False, "error": "No active transaction"}, status=400)

    cart_lines = list(TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr"))
    if not cart_lines:
        return JsonResponse({"ok": False, "error": "Active cart is empty"}, status=400)

    session = get_current_session(request)
    if not session:
        return JsonResponse({"ok": False, "error": "No open POS session"}, status=400)

    now = datetime.datetime.now()
    header = TransactionHeader.objects.create(
        session=session,
        user_id=user_id,
        user_id2=manager_user.username[:4],
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        transaction_date=session.business_date,
        transaction_time=now.strftime("%H:%M"),
        transaction_type=TRTYPE_VOID_TRANS,
        return_code=TRTYPE_VOID_TRANS,
    )

    TransactionItem.objects.bulk_create([
        TransactionItem(
            header=header,
            item_code=line.item_code or "",
            item_description=line.item_description or "",
            item_qty=line.item_qty or 0,
            item_uom=line.item_uom or "",
            item_supplier=line.item_supplier or "",
            item_department=line.item_department or "",
            item_class=line.item_class or "",
            item_size=line.item_size or "",
            item_color=line.item_color or "",
            item_type=line.item_type or "",
            item_cost=line.item_cost or 0,
            item_price=line.item_price or 0,
            item_discount=line.item_discount or 0,
            discount_code=line.discount_code or "",
            item_price_ext=line.item_price_ext or 0,
            tag1=line.tag1 or "",
            tag2=line.tag2 or "",
            tag3=line.tag3 or "",
            tag4=TAG_VOID_TRANS,
            promo_tag=line.promo_tag or "",
        )
        for line in cart_lines
    ])

    TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).delete()

    _save_current_transaction_no(trans_no)
    request.session["pos_trans_no"] = _get_next_transaction_no()
    _clear_trans_disc(request)

    return JsonResponse({
        "ok": True,
        "void_kind": "full",
        "transaction_type": TRTYPE_VOID_TRANS,
        "next_transaction_no": request.session.get("pos_trans_no"),
    })


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_void_previous(request):
    """Void a previous completed transaction (F6) by receipt number, same business day."""
    manager_pin = request.POST.get("manager_pin", "")
    manager_user = _verify_manager_pin(manager_pin)
    if not manager_user:
        return JsonResponse({"ok": False, "error": "Manager PIN is invalid"}, status=403)

    receipt_no = _normalize_transaction_no(request.POST.get("receipt_no", ""))
    if receipt_no == "00000000":
        return JsonResponse({"ok": False, "error": "Receipt number is required"}, status=400)

    session = get_current_session(request)
    if not session:
        return JsonResponse({"ok": False, "error": "No open POS session"}, status=400)

    target = (
        TransactionHeader.objects
        .filter(
            store_id=STORE_ID,
            terminal_id=TERMINAL_ID,
            transaction_no=receipt_no,
            transaction_date=session.business_date,
        )
        .exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL)
        .order_by("-id")
        .first()
    )
    if not target:
        return JsonResponse({
            "ok": False,
            "error": "Receipt not found for this business day or already voided",
        }, status=404)

    already_voided = TransactionHeader.objects.filter(
        store_id=STORE_ID,
        terminal_id=TERMINAL_ID,
        transaction_date=session.business_date,
        transaction_type=TRTYPE_VOID_PREVIOUS,
        item_ref=receipt_no,
    ).exists()
    if already_voided:
        return JsonResponse({"ok": False, "error": "Receipt already voided previously"}, status=409)

    now = datetime.datetime.now()
    void_header = TransactionHeader.objects.create(
        session=session,
        user_id=_get_user_id(request),
        user_id2=manager_user.username[:4],
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=request.session.get("pos_trans_no") or receipt_no,
        transaction_date=session.business_date,
        transaction_time=now.strftime("%H:%M"),
        transaction_type=TRTYPE_VOID_PREVIOUS,
        return_code=TRTYPE_VOID_PREVIOUS,
        item_ref=receipt_no,
    )

    source_items = list(target.items.all())
    if source_items:
        TransactionItem.objects.bulk_create([
            TransactionItem(
                header=void_header,
                item_code=item.item_code or "",
                item_description=item.item_description or "",
                item_qty=item.item_qty or 0,
                item_uom=item.item_uom or "",
                item_supplier=item.item_supplier or "",
                item_department=item.item_department or "",
                item_class=item.item_class or "",
                item_size=item.item_size or "",
                item_color=item.item_color or "",
                item_type=item.item_type or "",
                item_cost=item.item_cost or 0,
                item_price=item.item_price or 0,
                item_discount=item.item_discount or 0,
                discount_code=item.discount_code or "",
                item_price_ext=item.item_price_ext or 0,
                tag1=item.tag1 or "",
                tag2=item.tag2 or "",
                tag3=item.tag3 or "",
                tag4=TAG_VOID_PREVIOUS,
                promo_tag=item.promo_tag or "",
            )
            for item in source_items
        ])

    return JsonResponse({
        "ok": True,
        "void_kind": "previous",
        "transaction_type": TRTYPE_VOID_PREVIOUS,
        "receipt_no": receipt_no,
    })


@login_required
@require_open_session
def cart_new(request):
    """Start a new transaction (clear cart, get new receipt number)."""
    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")

    if trans_no:
        TempTransaction.objects.filter(
            user_id=user_id,
            terminal_id=TERMINAL_ID,
            store_id=STORE_ID,
            transaction_no=trans_no,
        ).delete() # This needs to be configured to suspend instead of delete in case we want to support suspended transactions in the future
        _save_current_transaction_no(trans_no)

    new_trans = _get_next_transaction_no()
    request.session["pos_trans_no"] = new_trans
    _clear_trans_disc(request)

    return redirect("sales:pos_cashier")


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_trans_disc(request):
    """Set or clear transaction-level discount. Returns updated cart-summary HTML."""
    try:
        pct = max(0, min(100, float(request.POST.get("trans_disc_pct", "0") or "0")))
    except (ValueError, TypeError):
        pct = 0
    disc_type = (request.POST.get("trans_disc_type") or "").strip()[:3]
    disc_label = (request.POST.get("trans_disc_label") or "").strip()[:30]

    request.session["pos_trans_disc_pct"] = str(pct)
    request.session["pos_trans_disc_type"] = disc_type
    request.session["pos_trans_disc_label"] = disc_label

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    return render(request, "sales/partials/cart_trans_disc_response.html", {
        "cart_lines": cart_lines,
        "subtotal": subtotal,
        "trans_disc": trans_disc,
        "trans_disc_amt": trans_disc_amt,
        "total": total,
        "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
        "last_item": cart_lines.last(),
    })


@login_required(login_url="sales:pos_login")
@require_open_session
@require_http_methods(["POST"])
def cart_line_disc(request):
    """Apply discount to a specific cart line by rec_ctr."""
    try:
        rec_ctr = int(request.POST.get("rec_ctr", 0))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid rec_ctr"}, status=400)

    try:
        disc_pct = Decimal(str(max(0, min(100, float(request.POST.get("disc_pct", "0") or "0")))))
    except (ValueError, TypeError):
        disc_pct = Decimal("0")
    disc_type = (request.POST.get("disc_type") or "").strip()[:3]

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        return JsonResponse({"ok": False, "error": "No active transaction"}, status=400)

    line = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        rec_ctr=rec_ctr,
    ).first()

    if not line:
        if request.headers.get("HX-Request"):
            return render(request, "sales/partials/cart_error.html", {"error": "Line not found"}, status=404)
        return JsonResponse({"ok": False, "error": "Line not found"}, status=404)

    price = line.item_price or Decimal("0")
    qty = line.item_qty or Decimal("1")
    item_discount = (price * disc_pct / 100).quantize(Decimal("0.0001")) if disc_pct > 0 else Decimal("0")
    ext = (price - item_discount) * qty
    if (line.tag1 or "") == TAG_ITEM_RETURN:
        ext = -abs(ext)

    line.item_discount = item_discount
    line.discount_code = disc_type
    line.item_price_ext = ext
    line.save()

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "sales/partials/cart_line_disc_response.html",
            {
                "cart_lines": cart_lines,
                "subtotal": subtotal,
                "trans_disc": trans_disc,
                "trans_disc_amt": trans_disc_amt,
                "total": total,
                "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
                "last_item": cart_lines.last(),
            },
        )

    return JsonResponse({"ok": True, "total": str(total)})


@login_required(login_url="sales:pos_login")
@require_open_session
@require_http_methods(["POST"])
def cart_line_price_override(request):
    """Override unit price for a specific cart line and preserve existing line-discount rate."""
    try:
        rec_ctr = int(Decimal(str(request.POST.get("rec_ctr", "0") or "0")))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid rec_ctr"}, status=400)

    try:
        new_price = Decimal(str(request.POST.get("new_price", "0") or "0"))
    except (ValueError, TypeError, ArithmeticError):
        return JsonResponse({"ok": False, "error": "Invalid price"}, status=400)

    if new_price < 0:
        return JsonResponse({"ok": False, "error": "Price cannot be negative"}, status=400)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        return JsonResponse({"ok": False, "error": "No active transaction"}, status=400)

    line = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        rec_ctr=rec_ctr,
    ).first()

    if not line:
        if request.headers.get("HX-Request"):
            return render(request, "sales/partials/cart_error.html", {"error": "Line not found"}, status=404)
        return JsonResponse({"ok": False, "error": "Line not found"}, status=404)

    old_price = line.item_price or Decimal("0")
    if new_price != old_price:
        old_discount = line.item_discount or Decimal("0")
        qty = line.item_qty or Decimal("1")

        disc_rate = Decimal("0")
        if old_price > 0 and old_discount > 0:
            disc_rate = old_discount / old_price

        new_item_discount = (new_price * disc_rate).quantize(Decimal("0.0001")) if disc_rate > 0 else Decimal("0")
        ext = (new_price - new_item_discount) * qty
        if (line.tag1 or "") == TAG_ITEM_RETURN:
            ext = -abs(ext)

        if (line.old_price or Decimal("0")) <= 0:
            line.old_price = old_price

        line.item_price = new_price
        line.item_discount = new_item_discount
        line.item_price_ext = ext
        line.price_override = TAG_PRICE_OVERRIDE
        line.save(update_fields=[
            "old_price",
            "item_price",
            "item_discount",
            "item_price_ext",
            "price_override",
        ])

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "sales/partials/cart_line_disc_response.html",
            {
                "cart_lines": cart_lines,
                "subtotal": subtotal,
                "trans_disc": trans_disc,
                "trans_disc_amt": trans_disc_amt,
                "total": total,
                "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
                "last_item": cart_lines.last(),
            },
        )

    return JsonResponse({"ok": True, "total": str(total)})


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_item_return_toggle(request):
    """Tag or untag a cart line as item return with manager/admin validation."""
    raw_rec_ctr = str(request.POST.get("rec_ctr", "") or "").strip()
    if not raw_rec_ctr:
        return JsonResponse({"ok": False, "error": "Select an item first"}, status=400)

    try:
        rec_ctr = int(Decimal(raw_rec_ctr))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid rec_ctr"}, status=400)

    if rec_ctr <= 0:
        return JsonResponse({"ok": False, "error": "Invalid rec_ctr"}, status=400)

    mode = (request.POST.get("mode") or "set").strip().lower()
    if mode not in {"set", "clear"}:
        return JsonResponse({"ok": False, "error": "Invalid mode"}, status=400)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        return JsonResponse({"ok": False, "error": "No active transaction"}, status=400)

    line = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        rec_ctr=rec_ctr,
    ).first()
    if not line:
        return JsonResponse({"ok": False, "error": "Line not found"}, status=404)

    price = line.item_price or Decimal("0")
    qty = line.item_qty or Decimal("1")
    item_discount = line.item_discount or Decimal("0")
    base_ext = abs((price - item_discount) * qty)

    if mode == "clear":
        line.tag1 = ""
        line.return_code = ""
        line.transaction_date_r = None
        line.item_ref = ""
        line.item_price_ext = base_ext
        line.save(update_fields=[
            "tag1", "return_code", "transaction_date_r", "item_ref", "item_price_ext"
        ])
    else:
        source_trans_no = _normalize_transaction_no(request.POST.get("source_transaction_no", ""))
        if source_trans_no == "00000000":
            return JsonResponse({"ok": False, "error": "Original transaction number is required"}, status=400)

        source_exists = TransactionHeader.objects.filter(
            store_id=STORE_ID,
            terminal_id=TERMINAL_ID,
            transaction_no=source_trans_no,
        ).exists()
        if not source_exists:
            return JsonResponse({
                "ok": False,
                "error": "Source transaction number was not found in historical transactions",
            }, status=404)

        purchased_raw = (request.POST.get("purchased_date") or "").strip()
        if not purchased_raw:
            return JsonResponse({"ok": False, "error": "Purchased date is required"}, status=400)
        try:
            purchased_date = datetime.datetime.strptime(purchased_raw, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid purchased date"}, status=400)

        if purchased_date > datetime.date.today():
            return JsonResponse({"ok": False, "error": "Purchased date cannot be in the future"}, status=400)

        manager_pin = request.POST.get("manager_pin", "")
        manager_user = _verify_manager_pin(manager_pin)
        if not manager_user:
            return JsonResponse({"ok": False, "error": "Admin/manager PIN is invalid"}, status=403)

        line.tag1 = TAG_ITEM_RETURN
        line.return_code = TAG_ITEM_RETURN
        line.transaction_date_r = purchased_date
        line.item_ref = source_trans_no
        line.item_price_ext = -base_ext
        line.save(update_fields=[
            "tag1", "return_code", "transaction_date_r", "item_ref", "item_price_ext"
        ])

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "sales/partials/cart_line_disc_response.html",
            {
                "cart_lines": cart_lines,
                "subtotal": subtotal,
                "trans_disc": trans_disc,
                "trans_disc_amt": trans_disc_amt,
                "total": total,
                "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
                "last_item": cart_lines.last(),
            },
        )

    return JsonResponse({"ok": True, "total": str(total), "mode": mode})


@login_required
@require_open_session
@require_http_methods(["GET"])
def cart_return_lookup(request):
    """Lookup a historical receipt and return its line items for return selection."""
    receipt_no = _normalize_transaction_no(request.GET.get("receipt_no", ""))
    if receipt_no == "00000000":
        return JsonResponse({"ok": False, "error": "Receipt number is required"}, status=400)

    source_header = (
        TransactionHeader.objects
        .filter(
            store_id=STORE_ID,
            terminal_id=TERMINAL_ID,
            transaction_no=receipt_no,
        )
        .exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL)
        .exclude(return_code=TAG_ITEM_RETURN)
        .order_by("-id")
        .first()
    )
    if not source_header:
        return JsonResponse({
            "ok": False,
            "error": "Receipt not found or is not eligible for returns",
        }, status=404)

    items = []
    for item in source_header.items.all().order_by("id"):
        qty = item.item_qty or Decimal("0")
        if qty <= 0:
            continue
        price = item.item_price or Decimal("0")
        discount = item.item_discount or Decimal("0")
        ext = item.item_price_ext or ((price - discount) * qty)
        items.append({
            "line_id": item.id,
            "item_code": item.item_code or "",
            "description": item.item_description or "",
            "qty": str(qty),
            "max_qty": str(qty),
            "price": str(price),
            "ext": str(ext),
            "size": get_size_description(item.item_size or ""),
            "color": get_color_description(
                item.item_color or "",
                icode=item.item_code or "",
                size=item.item_size or "",
            ),
        })

    if not items:
        return JsonResponse({
            "ok": False,
            "error": "Receipt has no returnable items",
        }, status=404)

    return JsonResponse({
        "ok": True,
        "receipt_no": source_header.transaction_no,
        "transaction_date": source_header.transaction_date.strftime("%Y-%m-%d") if source_header.transaction_date else "",
        "items": items,
    })


@login_required
@require_open_session
@require_http_methods(["POST"])
def cart_return_import(request):
    """Insert selected historical receipt items directly into current cart as returns."""
    manager_pin = request.POST.get("manager_pin", "")
    manager_user = _verify_manager_pin(manager_pin)
    if not manager_user:
        return JsonResponse({"ok": False, "error": "Admin/manager PIN is invalid"}, status=403)

    receipt_no = _normalize_transaction_no(request.POST.get("receipt_no", ""))
    if receipt_no == "00000000":
        return JsonResponse({"ok": False, "error": "Receipt number is required"}, status=400)

    source_header = (
        TransactionHeader.objects
        .filter(
            store_id=STORE_ID,
            terminal_id=TERMINAL_ID,
            transaction_no=receipt_no,
        )
        .exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL)
        .exclude(return_code=TAG_ITEM_RETURN)
        .order_by("-id")
        .first()
    )
    if not source_header:
        return JsonResponse({"ok": False, "error": "Receipt not found or is not eligible for returns"}, status=404)

    try:
        item_ids = json.loads((request.POST.get("item_ids") or "[]").strip() or "[]")
        item_ids = [int(x) for x in item_ids]
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid selected items"}, status=400)

    try:
        raw_qty_map = json.loads((request.POST.get("item_qtys") or "{}").strip() or "{}")
        if not isinstance(raw_qty_map, dict):
            raise ValueError("qty map must be object")
        requested_qty_map = {}
        for key, value in raw_qty_map.items():
            line_id = int(key)
            qty = Decimal(str(value or "0"))
            requested_qty_map[line_id] = qty
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid return quantities"}, status=400)

    if not item_ids:
        return JsonResponse({"ok": False, "error": "Select at least one item"}, status=400)

    source_items = list(source_header.items.filter(id__in=item_ids).order_by("id"))
    if not source_items:
        return JsonResponse({"ok": False, "error": "Selected items were not found on this receipt"}, status=404)

    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    if not trans_no:
        trans_no = _get_next_transaction_no()
        request.session["pos_trans_no"] = trans_no

    now = datetime.datetime.now()
    try:
        biz_date = get_business_date(STORE_ID, TERMINAL_ID, now)
    except Exception:
        biz_date = now.date()

    max_rec = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).aggregate(mx=models.Max("rec_ctr"))
    rec_ctr = int(max_rec["mx"] or 0)

    rows = []
    for src in source_items:
        source_qty = src.item_qty or Decimal("0")
        requested_qty = requested_qty_map.get(src.id, source_qty)
        if requested_qty <= 0:
            continue
        if requested_qty > source_qty:
            return JsonResponse({
                "ok": False,
                "error": f"Requested return quantity exceeds sold quantity for item {src.item_code or src.id}",
            }, status=400)

        rec_ctr += 1
        price = src.item_price or Decimal("0")
        discount = src.item_discount or Decimal("0")
        ext = (price - discount) * requested_qty
        rows.append(TempTransaction(
            user_id=user_id,
            terminal_id=TERMINAL_ID,
            store_id=STORE_ID,
            transaction_no=trans_no,
            transaction_date=biz_date,
            transaction_date_r=source_header.transaction_date,
            transaction_time=now.strftime("%H:%M"),
            transaction_type="S",
            return_code=TAG_ITEM_RETURN,
            item_ref=source_header.transaction_no,
            item_code=src.item_code or "",
            item_description=(src.item_description or "")[:25],
            item_qty=requested_qty,
            item_uom=src.item_uom or "",
            item_supplier=src.item_supplier or "",
            item_department=src.item_department or "",
            item_class=src.item_class or "",
            item_size=src.item_size or "",
            item_color=src.item_color or "",
            item_type=src.item_type or "",
            item_cost=src.item_cost or 0,
            item_price=price,
            item_discount=discount,
            discount_code=src.discount_code or "",
            item_price_ext=-abs(ext),
            tag1=TAG_ITEM_RETURN,
            tag2=src.tag2 or "",
            tag3=src.tag3 or "",
            tag4=src.tag4 or "",
            promo_tag=src.promo_tag or "",
            rec_ctr=rec_ctr,
        ))

    if not rows:
        return JsonResponse({"ok": False, "error": "No valid items selected for return"}, status=400)

    TempTransaction.objects.bulk_create(rows)

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")
    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    return JsonResponse({
        "ok": True,
        "imported_count": len(rows),
        "total": str(total),
        "item_count": sum(int(l.item_qty or 0) for l in cart_lines),
    })


@login_required
@require_open_session
def pay_view(request):
    """Payment screen - select tender and complete sale."""
    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    is_htmx = request.headers.get("HX-Request")

    if not trans_no:
        if is_htmx:
            return render(request, "sales/partials/_pay_modal_empty.html", {"message": "No active transaction."})
        return redirect("sales:pos_cashier")

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    if not cart_lines.exists():
        if is_htmx:
            return render(request, "sales/partials/_pay_modal_empty.html", {"message": "Add items to cart first."})
        return redirect("sales:pos_cashier")

    tenders = Tender.objects.filter(pallow="Y").order_by("pcode")
    context = {
        "store_name": _get_store_name(),
        "cart_lines": cart_lines,
        "subtotal": subtotal,
        "trans_disc": trans_disc,
        "trans_disc_amt": trans_disc_amt,
        "total": total,
        "tenders": tenders,
        "standalone": not is_htmx,
    }
    # Return modal partial when requested via HTMX (floating tender on cashier page)
    if is_htmx:
        return render(request, "sales/partials/_pay_modal.html", context)
    return render(request, "sales/pay.html", context)


def _parse_tender_entries(request):
    """Parse tender_entries JSON from POST.
    Returns list of {"pcode": ..., "amount": ..., "payment_reference": ...} or empty.
    """
    import json
    raw = request.POST.get("tender_entries", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        entries = []
        for item in data:
            pcode = (item.get("pcode") or "").strip()
            try:
                amt = Decimal(str(item.get("amount", 0) or 0))
            except (ValueError, TypeError):
                amt = Decimal("0")
            payment_reference = str(item.get("payment_reference") or "").strip()[:20]
            if pcode and amt > 0:
                entries.append({"pcode": pcode, "amount": amt, "payment_reference": payment_reference})
        return entries
    except (json.JSONDecodeError, TypeError):
        return []


@login_required
@require_open_session
@require_http_methods(["POST"])
def payment_complete(request):
    """
    Complete payment with tender entries. Supports multiple tenders.
    Only completes when total tendered >= amount due.
    
    NOW WITH CLIPPER-STYLE TRANSACTION LOGGING
    """
    # vat constants for transaction logging - not actually used in current calculations but stored for reference
    vatable_gross = Decimal("0")
    vat_exempt    = Decimal("0")
    zero_rated    = Decimal("0")
    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    tender_entries = _parse_tender_entries(request)
    current_session = get_current_session(request)
    cart_lines_qs = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    cart_lines_list = list(cart_lines_qs)
    if not cart_lines_list:
        return redirect("sales:pos_cashier")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines_list, trans_disc)
    print("SUBTOTAL:", subtotal, "DISC_AMT:", trans_disc_amt, "TOTAL:", total)

    if total > 0 and not tender_entries:
        return redirect("sales:pay")

    total_tendered = sum(t["amount"] for t in tender_entries)
    if total > 0 and total_tendered < total:
        return redirect("sales:pay")

    # Enforce reference for non-cash tenders and disallow overpay on non-cash entries.
    if total > 0:
        running_remaining = total
        for t in tender_entries:
            tender = Tender.objects.filter(pcode=t["pcode"]).first()
            is_cash = bool(tender and tender.pchange == "Y")
            if not is_cash and not (t.get("payment_reference") or "").strip():
                return redirect("sales:pay")
            if not is_cash and t["amount"] > running_remaining:
                return redirect("sales:pay")
            running_remaining = max(Decimal("0"), running_remaining - t["amount"])

    now = datetime.datetime.now()
    try:
        biz_date = get_business_date(STORE_ID, TERMINAL_ID, now)
    except Exception:
        biz_date = now.date()


    # for item in cart_lines_list:
    for line in cart_lines_list:
        ext = line.item_price_ext or Decimal("0")
        tax_code = (line.item_tax_code or "V").upper()
        if tax_code == "V":
            vatable_gross += ext
        elif tax_code == "E":
            vat_exempt += ext
        elif tax_code == "Z":
            zero_rated += ext
        else:
            vatable_gross += ext

    vatable_net = (vatable_gross / (1 + VAT_RATE)).quantize(Decimal("0.0001"))
    vat_amount  = (vatable_gross - vatable_net).quantize(Decimal("0.0001"))


    # --- Build tender summary ---
    tender_lines = []
    tender_entries_full = []  # For TransactionService
    total_cash = Decimal("0")
    for t in tender_entries:
        pcode = t["pcode"]
        amt = t["amount"]

        tender = Tender.objects.filter(pcode=pcode).first()
        desc = tender.description if tender else pcode
        is_cash = bool(tender and tender.pchange == "Y")

        tender_lines.append({
            "pcode": pcode,
            "desc": desc,
            "amount": str(amt),
            "is_cash": is_cash
        })
        tender_entries_full.append((pcode, amt, desc, is_cash))

        if is_cash:
            total_cash += amt

    if total < 0:
        change_amount = abs(total)
    elif total_cash > 0:
        change_amount = max(Decimal("0"), total_tendered - total)
    else:
        change_amount = Decimal("0")
    tender_display = ", ".join(f"{t['desc']} ₱{t['amount']}" for t in tender_lines)
    has_return_lines = any((line.tag1 or "") == TAG_ITEM_RETURN for line in cart_lines_list)
    all_lines_return = has_return_lines and all((line.tag1 or "") == TAG_ITEM_RETURN for line in cart_lines_list)

    # --- Create one TransactionHeader for the whole transaction ---
    header = TransactionHeader.objects.create(
        session=current_session,
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
        transaction_date=biz_date,
        transaction_time=now.strftime("%H:%M"),
        transaction_type="S",
        return_code=TAG_ITEM_RETURN if all_lines_return else "",

        trans_disc_type=trans_disc.get("type", ""),
        trans_disc_pct=trans_disc.get("pct", 0),
        trans_disc_label=trans_disc.get("label", ""),
        trans_disc_amount=trans_disc_amt,

        vat_rate=VAT_RATE,
        vatable_amount=vatable_net,    
        vat_amount=vat_amount,           
        vat_exempt_amount=vat_exempt,
        zero_rated_amount=zero_rated,

        subtotal=subtotal,
        amount_total=total,
        amount_tendered=total_tendered,
        change_amount=change_amount,
    )

    # --- Create one TransactionItem per cart line ---
    TransactionItem.objects.bulk_create([
        TransactionItem(
            header=header,
            item_code=line.item_code or "",
            item_description=line.item_description or "",
            item_qty=line.item_qty or 0,
            item_uom=getattr(line, 'item_uom', ''),
            item_supplier=getattr(line, 'item_supplier', ''),
            item_department=getattr(line, 'item_department', ''),
            item_class=getattr(line, 'item_class', ''),
            item_size=line.item_size or "",
            item_color=line.item_color or "",
            item_color_desc=line.item_color_desc or "",
            item_type=getattr(line, 'item_type', ''),
            item_cost=getattr(line, 'item_cost', 0) or 0,
            item_price=line.item_price or 0,
            item_discount=line.item_discount or 0,
            discount_code=line.discount_code or "",
            item_price_ext=line.item_price_ext or 0,
            tag1=getattr(line, 'tag1', ''),
            tag2=getattr(line, 'tag2', ''),
            tag3=getattr(line, 'tag3', ''),
            tag4=getattr(line, 'tag4', ''),
            promo_tag=getattr(line, 'promo_tag', ''),
        )
        for line in cart_lines_list
    ])

    # --- Create one Payment per tender entry ---
    Payment.objects.bulk_create([
        Payment(
            header=header,
            pcode=t["pcode"],
            amount=t["amount"],
            tender_desc=next(
                (tl["desc"] for tl in tender_lines if tl["pcode"] == t["pcode"]),
                t["pcode"]
            ),
            payment_reference=(t.get("payment_reference") or "")[:20],
        )
        for t in tender_entries
    ])

    # --- Clipper-style flat transaction log (TransactionLog / TLOG) ---
    try:
        service = TransactionService()
        service.save_to_transaction_log(
            cart_lines=cart_lines_qs,
            transaction_no=trans_no,
            transaction_date=biz_date,
            transaction_time=now.strftime("%H:%M"),
            user_id=user_id,
            tender_entries=tender_entries_full,
            subtotal_discount_pct=trans_disc.get("pct", Decimal("0")),
            subtotal_discount_label=trans_disc.get("label", ""),
            si_number=trans_no,
        )
    except Exception as e:
        print(f"⚠️  TransactionService log failed: {e}")

    # --- Store receipt data ---
    request.session["last_receipt"] = {
        "transaction_no": trans_no,
        "date": biz_date.strftime("%A %b %d %Y"),
        "time": now.strftime("%I:%M:%S %p"),
        "subtotal": str(subtotal),
        "trans_disc_pct": str(trans_disc.get("pct", 0)),
        "trans_disc_label": trans_disc.get("label", ""),
        "trans_disc_amt": str(trans_disc_amt),
        "total": str(total),
        "tender": tender_display,
        "tender_lines": tender_lines,
        "is_cash": any(t["is_cash"] for t in tender_lines) or total < 0,
        "amount_tendered": str(total_tendered) if tender_lines else "",
        "change_amount": str(change_amount),
        "is_return_only": all_lines_return,
        "is_exchange": has_return_lines and not all_lines_return,
        "vat_rate":       str(VAT_RATE),
        "vatable_amount": str(vatable_net),
        "vat_amount":     str(vat_amount),
        "vat_exempt":     str(vat_exempt),
        "zero_rated":     str(zero_rated),
        "lines": [
            {
                "description": line.item_description or "",
                "qty": str(line.item_qty),
                "price": str(line.item_price or 0),
                "gross": str(line.item_gross),
                "disc_pct": line.disc_pct,
                "disc_total": str(line.item_disc_total),
                "ext": str(line.item_price_ext or 0),
                "size": get_size_description(line.item_size or ""),
                "color": get_color_description(
                    line.item_color or "",
                    icode=line.item_code or "",
                    size=line.item_size or "",
                ),
                "is_return": (line.tag1 or "") == TAG_ITEM_RETURN,
                "source_trans_no": line.item_ref or "",
                "purchased_date": line.transaction_date_r.strftime("%Y-%m-%d") if line.transaction_date_r else "",
            }
            for line in cart_lines_list
        ],
    }

    # --- Persist current transaction no, clear cart, advance transaction number ---
    _save_current_transaction_no(trans_no)
    # --- Clear cart, advance transaction number ---
    cart_lines_qs.delete()
    request.session["pos_trans_no"] = _get_next_transaction_no()
    _clear_trans_disc(request)

    return redirect("sales:receipt")


@login_required
def item_search(request):
    """Search items by description, code, or barcode. Returns JSON."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    from django.db.models import Q

    # Search Item master by description or code (exclude inactive items)
    items = Item.objects.filter(
        Q(short_desc__icontains=q) | Q(long_desc__icontains=q) | Q(icode__icontains=q)
    ).exclude(inactive="Y").order_by("short_desc")[:30]

    results = []
    for item in items:
        # Get all variants (barcodes) for this item
        variants = ItemDetail.objects.filter(icode=item.icode).order_by("size", "color")
        if variants.exists():
            for v in variants:
                results.append({
                    "barcode": v.barcode,
                    "code": item.icode,
                    "description": item.short_desc or item.long_desc,
                    "size": v.size,
                    "color": v.color,
                    "color_desc": v.color_desc,
                    "price": str(v.price or item.price),
                })
        else:
            results.append({
                "barcode": item.icode,
                "code": item.icode,
                "description": item.short_desc or item.long_desc,
                "size": item.size or "",
                "color": item.color or "",
                "color_desc": item.color_desc or "",
                "price": str(item.price),
            })

    return JsonResponse({"results": results})


# ---------------------------------------------------------------------------
# Close session details (GET — JSON for the close-session modal)
# ---------------------------------------------------------------------------
@login_required
@require_open_session
@require_http_methods(["GET"])
def to_close_session_details(request):
    session = _get_terminal_session(STORE_ID, TERMINAL_ID)
    if not session:
        return JsonResponse({"error": "No open session found."}, status=400)

    cash_tender_codes = list(
        Tender.objects.filter(pchange="Y").values_list("pcode", flat=True)
    )

    # --- Base querysets scoped to this session ---
    session_headers = TransactionHeader.objects.filter(session_id=session.id)
    session_items   = TransactionItem.objects.filter(header__session_id=session.id)
    session_payments = Payment.objects.filter(header__session_id=session.id)

    # --- Void transactions ---
    # Headers whose transaction_type is a void type
    void_headers = session_headers.filter(
        transaction_type__in=VOID_TRANSACTION_TYPES_ALL
    )
    void_count  = void_headers.count()
    void_amount = void_headers.aggregate(
        total=Sum("amount_total")
    )["total"] or Decimal("0")

    # --- Return transactions ---
    # Headers where return_code == TAG_ITEM_RETURN and transaction_type is normal sale
    return_headers = session_headers.filter(return_code=TAG_ITEM_RETURN)
    return_count   = return_headers.count()
    return_amount  = return_headers.aggregate(
        total=Sum("amount_total")
    )["total"] or Decimal("0")

    # --- Sales (exclude voids and pure returns) ---
    sale_headers = session_headers.exclude(
        transaction_type__in=VOID_TRANSACTION_TYPES_ALL
    ).exclude(return_code=TAG_ITEM_RETURN)

    gross_sales = sale_headers.aggregate(
        total=Sum("subtotal")
    )["total"] or Decimal("0")

    total_change = sale_headers.aggregate(
        total=Sum("change_amount")
    )["total"] or Decimal("0")

    total_discounts = sale_headers.aggregate(
        total=Sum("trans_disc_amount")
    )["total"] or Decimal("0")

    # Item-level discounts from sale items only
    item_discounts = session_items.filter(
        header__transaction_type__in=["S", ""]  # normal sale type
    ).exclude(
        header__return_code=TAG_ITEM_RETURN
    ).aggregate(
        total=Sum(
            models.ExpressionWrapper(
                models.F("item_discount") * models.F("item_qty"),
                output_field=models.DecimalField()
            )
        )
    )["total"] or Decimal("0")

    total_discounts += item_discounts

    net_sales = gross_sales - total_discounts

    # --- Cash tender breakdown ---
    paid_in_cash = session_payments.filter(
        pcode__in=cash_tender_codes,
        header__transaction_type__in=["S", ""],
    ).exclude(
        header__return_code=TAG_ITEM_RETURN
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # Cash returned from return transactions
    cash_returned = session_payments.filter(
        pcode__in=cash_tender_codes,
        header__return_code=TAG_ITEM_RETURN,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # --- Non-cash breakdown ---
    non_cash_qs = session_payments.exclude(pcode__in=cash_tender_codes)

    credit_debit_total = (
        non_cash_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    )

    credit_debit_breakdown = list(
        non_cash_qs
        .values("tender_desc")
        .annotate(total=Sum("amount"))
        .order_by("tender_desc")
    )
    cash = paid_in_cash - cash_returned - total_change
    # --- Cash totals ---
    # expected = change fund + cash sales - cash returned
    expected_cash = session.opening_cash + paid_in_cash - cash_returned - total_change
    net_worth     = expected_cash + credit_debit_total

    return JsonResponse({
        "opening_cash":          float(session.opening_cash),
        "paid_in_cash":          float(cash),
        "cash_returned":         float(cash_returned),
        "expected_cash":         float(expected_cash),
        "credit_debit_cash":     float(credit_debit_total),
        "credit_debit_cash_list": [
            {
                "tender_desc": row["tender_desc"] or "",
                "total":       float(row["total"] or 0),
            }
            for row in credit_debit_breakdown
        ],
        "gross_sales":     float(gross_sales),
        "total_discounts": float(total_discounts),
        "net_sales":       float(net_sales),    
        "net_worth":       float(net_worth),
        "void_count":      void_count,
        "void_amount":     float(abs(void_amount)),
        "return_count":    return_count,
        "return_amount":   float(abs(return_amount)),
    })
# ---------------------------------------------------------------------------
# Close session view
# ---------------------------------------------------------------------------

@login_required
@require_open_session
@require_http_methods(["POST"])
def close_session(request):
    user = request.user

    session = _get_terminal_session(STORE_ID, TERMINAL_ID)
    if not session:
        messages.error(request, "No active session found to close.")
        return redirect("sales:pos_cashier")

    closing_cash = _parse_decimal(request.POST.get("closing_cash"))
    if closing_cash < 0:
        messages.error(request, "Closing cash cannot be negative.")
        return redirect("sales:pos_cashier")

    try:
        session.close(closed_by_user=user, closing_cash=closing_cash)
    except Exception as e:
        messages.error(request, str(e))
        return redirect("sales:pos_cashier")

    for key in (
        "pos_trans_no",
        "pos_trans_disc_pct",
        "pos_trans_disc_type",
        "pos_trans_disc_label",
        "last_receipt",
    ):
        request.session.pop(key, None)

    return redirect("pos_logout")


def debug_sessions_json(request):
    sessions = POSSession.objects.prefetch_related(
        'transaction_headers__items', 'transaction_headers__payments'
    ).filter(status="open")

    data = []

    for session in sessions:
        session_data = {
            "id": session.id,
            # "cashier": str(session.cashier),
            "terminal_id": session.terminal_id,
            "store_id": session.store_id,
            "business_date": str(session.business_date),
            "status": session.status,
            "opened_by": str(session.opened_by),
            "transactions": []
        }

        for header in session.transaction_headers.all():
            header_data = {
                "id": header.id,
                "transaction_no": header.transaction_no,
                "transaction_time": header.transaction_date,
                "transaction_type": header.transaction_type,
                "transacted_by": str(header.user_id),
                "served_by": header.served_by,
                "date": str(header.transaction_date),
                "items": [],
                "payments": []
            }

            for item in header.items.all():
                item_data = {
                    "item_code": item.item_code,
                    "description": item.item_description,
                    "qty": float(item.item_qty),
                    "price": float(item.item_price),
                    "item_discount": item.item_discount,
                    "discount_code": item.discount_code,

                }
                header_data["items"].append(item_data)

            for payment in header.payments.all():
                payment_data = {
                    "pcode": payment.pcode,
                    "description": payment.tender_desc,
                    "amount": float(payment.amount),
                }
                header_data["payments"].append(payment_data)


            session_data["transactions"].append(header_data)

        data.append(session_data)

    return JsonResponse(data, safe=False)

    
# =============================================================================
# PRINTER INFRASTRUCTURE  (shared by receipt + z-reading)
# =============================================================================
 
class _SocketPrinterWrapper:
    """Wraps a network socket to expose the same .write()/.close() API as serial.Serial."""
 
    def __init__(self, sock):
        self._sock = sock
 
    def write(self, data: bytes):
        self._sock.sendall(data)
 
    def close(self):
        self._sock.close()
 
 
def _open_printer(printer_port):
    """
    Open a printer connection based on TerminalPort.connection_type.
    Returns an object with .write(bytes) and .close().
    Raises ValueError / NotImplementedError on bad config.
    """
    ct = printer_port.connection_type
 
    if ct in ("SERIAL", "USB"):
        if not printer_port.port_name:
            raise ValueError(f"{ct} printer port_name is not configured.")
        conn = serial.Serial(
            port=printer_port.port_name,
            baudrate=printer_port.baudrate or 9600,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=1,
        )
        time.sleep(1)
        return conn
 
    elif ct == "NETWORK":
        if not printer_port.ip_address or not printer_port.port_no:
            raise ValueError("Network printer ip_address and port_no must be configured.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((printer_port.ip_address, printer_port.port_no))
        sock.settimeout(5)
        return _SocketPrinterWrapper(sock)
 
    elif ct == "WINDOWS":
        raise NotImplementedError(
            f"Windows printer support is not yet implemented "
            f"(printer_name: {printer_port.printer_name!r})."
        )
 
    else:
        raise ValueError(f"Unsupported connection_type: {ct!r}")
 
 
def _get_paper_width(terminal_config):
    """Read paper width from display_codes, default 40."""
    display_codes = {d.code_group: d for d in terminal_config.display_codes.all()}
    if "PW" in display_codes and display_codes["PW"].code_value:
        try:
            return int(display_codes["PW"].code_value)
        except ValueError:
            pass
    return 40
 
 
def _get_printer(terminal_config):
    """
    Resolve the PRINTER port from terminal_config and open a connection.
    Returns (printer, ports_dict).
    Raises ValueError if the port is not configured.
    """
    ports = {p.port_type: p for p in terminal_config.ports.all()}
    printer_port = ports.get("PRINTER")
    if not printer_port:
        raise ValueError("Printer port not configured in terminal settings.")
    return _open_printer(printer_port), ports
 
 
def _get_customer_footers(terminal_config):
    """Return footers for the customer copy, sorted by line_number."""
    footers = [
        f for f in terminal_config.footers.all()
        if f.footer_type in ("customer", "both")
    ]
    footers.sort(key=lambda f: f.line_number)
    return footers
 
 
def _get_report_footers(terminal_config):
    """Return footers for the customer copy, sorted by line_number."""
    footers = [
        f for f in terminal_config.footers.all()
        if f.footer_type in ("both")
    ]
    footers.sort(key=lambda f: f.line_number)
    return footers
 
 
# =============================================================================
# RECEIPT PRINTING
# =============================================================================
 
def _print_receipt(printer, terminal_config, context, session):
    """
    Stream the full customer receipt to an already-open printer connection.
    Separated from the view so it can be tested independently.
    Does NOT close the printer — the caller owns that.
    """
    paper_width = _get_paper_width(terminal_config)
    LEFT_WIDTH  = 32 if paper_width >= 48 else 22
    RIGHT_WIDTH = paper_width - LEFT_WIDTH
    ports       = {p.port_type: p for p in terminal_config.ports.all()}
 
    def write_line(text=""):
        printer.write((str(text) + "\n").encode("utf-8"))
 
    def separator():
        write_line("-" * paper_width)
 
    def align_lr(left="", right=""):
        left, right = str(left), str(right)
        return left.ljust(paper_width - len(right)) + right
 
    def item_line(qty, price, total):
        return f"{qty} x {price}".ljust(LEFT_WIDTH) + f"{total}".rjust(RIGHT_WIDTH)
 
    def format_money(val):
        try:
            return f"{float(val):,.2f}"
        except (TypeError, ValueError):
            return str(val)
 
    def format_qty(val):
        try:
            return f"{float(val):,.0f}"
        except (TypeError, ValueError):
            return str(val)
        
    # def set_text_size(width=1, height=1):
    #     width = max(1, min(width, 8))
    #     height = max(1, min(height, 8))

    #     n = ((width - 1) << 4) | (height - 1)
    #     printer.write(b"\x1d\x21" + bytes([n]))

    # ── Header ───────────────────────────────────────────────────────────────
    printer.write(b"\x1b\x40")  # ESC @ → Initialize printer
    printer.write(b"\x1b\x61\x01")  # center
    db_headers = list(terminal_config.headers.all().order_by("line_number"))
    for h in db_headers:
        if h.is_capitalized:
            printer.write(b"\x1b\x21\x10")
            write_line(h.header_text)
            printer.write(b"\x1b\x40")  # ESC @ → Initialize printer
        elif h.is_capitalized == False:
            printer.write(b"\x1b\x61\x01")  # center
            write_line(h.header_text)
    if not db_headers:
        write_line("OTTO Store")
 
    
    write_line("\nSALES INVOICE\n")
    
    # printer.write(b"\x1b\x21\x00")
    printer.write(b"\x1b\x61\x00")  # left
    write_line(f"SI #: {context['transaction_no']}")
    write_line(f"User Id    : {session.cashier.get_full_name() or session.cashier.username}")
    write_line(f"StoreId    : {session.store_id}")
    # write_line(f"Terminal No: {session.terminal_id}")
    separator()
 
    # ── Items ─────────────────────────────────────────────────────────────────
    for line in context["lines"]:
        write_line(line.get("description", "")[:paper_width])
        write_line(item_line(
            format_qty(line.get("qty")),
            format_money(line.get("price")),
            format_money(line.get("ext")),
        ))
        if line.get("disc_pct"):
            write_line(f"  {line['disc_pct']}% - {format_money(line.get('disc_total'))}")
 
    # ── Transaction discount ──────────────────────────────────────────────────
    if context["trans_disc_amt"] not in ("0", "0.0000", None, ""):
        separator()
        write_line(align_lr("Subtotal", format_money(context["subtotal"])))
        write_line(f"{context['trans_disc_label']} ({context['trans_disc_pct']}%)")
        write_line(align_lr("Discount", f"-{format_money(context['trans_disc_amt'])}"))
    
    # ── Total ─────────────────────────────────────────────────────────────────
    separator()
    write_line(align_lr("VAT-Exempt", format_money(context["vat_exempt_amount"])))
    write_line(align_lr("VATable", format_money(context["vatable_amount"])))
    write_line(align_lr(f"VAT @ {context['vat_rate']}%", format_money(context["vat_amount"])))
    printer.write(b"\x1b\x45\x01")  # bold on
    write_line(align_lr("TOTAL", format_money(context["total"])))
    printer.write(b"\x1b\x45\x00")  # bold off
    separator()
 
    # ── Tender lines ──────────────────────────────────────────────────────────
    for t in context["tender_lines"]:
        write_line(align_lr(t["desc"], format_money(t["amount"])))
 
    if context["amount_tendered"]:
        write_line(align_lr("Tendered", format_money(context["amount_tendered"])))
 
    if context["is_cash"] and context["change_amount"] not in ("", "0", "0.0000"):
        printer.write(b"\x1b\x45\x01")
        write_line(align_lr("CHANGE", format_money(context["change_amount"])))
        printer.write(b"\x1b\x45\x00")
 
    # ── Footer ────────────────────────────────────────────────────────────────
    separator()
 
    footers = _get_customer_footers(terminal_config)

    if footers:
        for f in footers:
            # Default alignment
            align_cmd = b"\x1b\x61\x00"  # left

            if f.is_centered:
                align_cmd = b"\x1b\x61\x01"  # center
            elif f.is_left_align:
                align_cmd = b"\x1b\x61\x00"  # left

            printer.write(align_cmd)
            write_line(f.footer_text)

        # Always reset to left after all footers
        printer.write(b"\x1b\x61\x00")

    else:
        printer.write(b"\x1b\x61\x00")
        write_line("Thank you for your purchase!")
    write_line("\n\ndf")
 
    # ── Cash drawer pulse ─────────────────────────────────────────────────────
    if ports.get("DRAWER"):
        try:
            printer.write(b"\x1b\x70\x00\x19\xfa")
        except Exception as e:
            print(f"⚠️  Cash drawer pulse failed: {e}")
 
    # ── Feed & cut ────────────────────────────────────────────────────────────
    write_line("\n" * 5)
    printer.write(b"\x1d\x56\x00")
 
 
# =============================================================================
# Z-READING PRINTING  (pure utility — NOT a Django view)
# =============================================================================
 
def _do_print_z_reading(session):
    """
    Print a Z-Reading report for an already-resolved POSSession object.
    Plain Python function — call it from a view after resolving the session.
    """
    terminal_config = _get_terminal_config()
    if not terminal_config:
        raise ValueError("Terminal configuration not found.")
 
    setup_details = _get_store_details()
    paper_width   = _get_paper_width(terminal_config)
 
    # ── Aggregate session data ────────────────────────────────────────────────
    headers_qs = TransactionHeader.objects.filter(session=session)
 
    si_numbers = headers_qs.order_by("transaction_no").values_list("transaction_no", flat=True)
    beg_si = si_numbers.first() or "00000000"
    end_si = si_numbers.last()  or "00000000"
 
    void_line_items   = headers_qs.filter(transaction_type__in=[TRTYPE_VOID_ITEM, TRTYPE_VOID_ITEM_LEGACY]).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    void_transactions = headers_qs.filter(transaction_type__in=[TRTYPE_VOID_TRANS, TRTYPE_VOID_TRANS_LEGACY]).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    void_previous     = headers_qs.filter(transaction_type=TRTYPE_VOID_PREVIOUS).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    item_returns      = headers_qs.filter(return_code="R").aggregate(total=Sum("items__item_price_ext"),      count=Count("id"))
    cash_withdrawals  = Payment.objects.filter(header__session=session, pcode="CW").aggregate(total=Sum("amount"), count=Count("id"))
 
    total_neg = sum(filter(None, [
        void_line_items["total"], void_transactions["total"],
        void_previous["total"],   item_returns["total"],
        cash_withdrawals["total"],
    ]))
 
    sales_headers = headers_qs.exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL).exclude(return_code="R")
 
    gross_sales = (
        TransactionItem.objects.filter(header__in=sales_headers)
        .aggregate(total=Sum("item_price_ext"))["total"] or Decimal("0")
    )
 
    item_disc       = TransactionItem.objects.filter(header__in=sales_headers, discount_code="ID").aggregate(total=Sum("item_discount"), count=Count("id"))
    item_amt_disc   = TransactionItem.objects.filter(header__in=sales_headers, discount_code="IA").aggregate(total=Sum("item_discount"), count=Count("id"))
    senior_disc     = TransactionItem.objects.filter(header__in=sales_headers, discount_code="SC").aggregate(total=Sum("item_discount"), count=Count("id"))
    senior_amt_disc = TransactionItem.objects.filter(header__in=sales_headers, discount_code="SA").aggregate(total=Sum("item_discount"), count=Count("id"))
 
    total_disc = sum(filter(None, [
        item_disc["total"], item_amt_disc["total"],
        senior_disc["total"], senior_amt_disc["total"],
    ]))
 
    customer_count   = sales_headers.aggregate(total=Sum("customer_count"))["total"] or 0
    total_items_sold = TransactionItem.objects.filter(header__in=sales_headers).aggregate(total=Sum("item_qty"))["total"] or 0
 
    tender_breakdown = (
        Payment.objects.filter(header__in=sales_headers)
        .values("tender_desc", "pcode")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("tender_desc")
    )
    gc_sales = Payment.objects.filter(header__in=sales_headers, pcode="GC").aggregate(total=Sum("amount"), count=Count("id"))
 
    net_sales             = gross_sales - Decimal(str(total_disc))
    total_neg_entries_amt = Decimal(str(total_neg or 0))
 
    # TODO: replace with actual GrandTotal model lookup
    old_grand_total = Decimal("75198919.10")
    new_grand_total = old_grand_total + gross_sales
 
    VAT_RATE      = Decimal("0.12")
    vatable_sales = net_sales / (1 + VAT_RATE)
    vat_amount    = net_sales - vatable_sales
    non_vat       = Decimal("0")
 
    # ── Open printer ──────────────────────────────────────────────────────────
    printer, _ = _get_printer(terminal_config)
 
    def write_line(text=""):
        printer.write((str(text) + "\n").encode("utf-8"))
 
    def separator(char="-"):
        write_line(char * paper_width)
 
    def fmt_count(val):
        try:
            return f"{int(val):>5}"
        except (TypeError, ValueError):
            return f"{'0':>5}"
 
    def neg_row(label, amount, count):
        return (
            f"     {label:<{paper_width - 21}}"
            f"{float(amount or 0):>10,.2f}"
            f"{int(count or 0):>5}"
        )
 
    def tendered(label, amount, count):
        return (
            f"{label:<{paper_width - 25}}"
            f"{float(amount or 0):>18,.2f}"
            f"{int(count or 0):>6}"
        )
 
    def summary_row(label, amount, count=None):
        amt_str = f"{float(amount or 0):>10,.2f}"
        if count is not None:
            return f"{label:<{paper_width - 14}}{amt_str}{int(count):>5}"
        return f"{label:<{paper_width - 13}}{amt_str}"
 
    def neg_gross(label, amount, count=None):
        amt_str = f"{float(amount or 0):>10,.2f}"
        if count is not None:
            return f"{label:<{paper_width - 14}}{amt_str}{int(count):>5}"
        return f"{label:<{paper_width - 16}}{amt_str}"
 
    def center(text):
        return text.center(paper_width)
 
    try:
        # ── Store header ──────────────────────────────────────────────────────
        printer.write(b"\x1b\x61\x01")
        db_headers = list(terminal_config.headers.all().order_by("line_number"))
        for h in db_headers:
            write_line(h.header_text)
        if not db_headers:
            write_line(setup_details.header01 or "OTTO Store")
        
        write_line(center("\n***** Z-Reading Report *****\n"))

        printer.write(b"\x1b\x61\x00")
        
        # ── Terminal info ─────────────────────────────────────────────────────
        write_line(f"StoreId    : {session.store_id}")
        write_line(f"Terminal No: {session.terminal_id}")
        write_line(f"User Id    : {session.cashier.get_full_name() or session.cashier.username}")
        write_line(f"Date       : {session.business_date.strftime('%m/%d/%Y')}")
        write_line(f"\nBEG. SI    : {beg_si}")
        write_line(f"END. SI    : {end_si}\n")
 
        # ── Negative entries ──────────────────────────────────────────────────
        write_line("Negative Entries")
        write_line(neg_row("Void Line Item",   void_line_items["total"],   void_line_items["count"]))
        write_line(neg_row("Void Transaction", void_transactions["total"], void_transactions["count"]))
        write_line(neg_row("Void Previous",    void_previous["total"],     void_previous["count"]))
        write_line(neg_row("Item Returns",     item_returns["total"],      item_returns["count"]))
        write_line(neg_row("Cash Withdrawal",  cash_withdrawals["total"],  cash_withdrawals["count"]))
        separator()
        write_line(neg_gross("Total", total_neg_entries_amt))
        write_line("")
        # ── Gross sales & discounts ───────────────────────────────────────────
        write_line(neg_gross("GROSS SALES", gross_sales))
        write_line("\nLess:Discounts")
        write_line(neg_row("Item Disc.",     item_disc["total"],       item_disc["count"]))
        write_line(neg_row("Item Amt Disc.", item_amt_disc["total"],   item_amt_disc["count"]))
        write_line(neg_row("Senior % Disc.", senior_disc["total"],     senior_disc["count"]))
        write_line(neg_row("     Amt.Disc.", senior_amt_disc["total"], senior_amt_disc["count"]))
        separator()
        write_line(neg_gross("Total", total_disc))
 
        # ── Counts ────────────────────────────────────────────────────────────
        write_line(f"\n{'Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>15}")
        write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>15}")
        separator()
 
        # ── Tender breakdown ──────────────────────────────────────────────────
        for t in tender_breakdown:
            desc = (t["tender_desc"] or t["pcode"] or "CASH").upper()
            write_line(tendered(desc, t["total"], t["count"]))
        # write_line(neg_row("GC SALES", gc_sales["total"], gc_sales["count"]))
        separator()
        write_line(neg_gross("NET SALES", net_sales))
        # write_line("")
        separator()
 
        # ── Terminal summary ──────────────────────────────────────────────────
        write_line(center("Terminal Summary Total"))
        printer.write(b"\x1b\x61\x00")
        separator("=")
        write_line(summary_row("OLD GRAND TOTAL", old_grand_total))
        write_line(summary_row("NEW GRAND TOTAL", new_grand_total))
        separator()
        write_line(f"{'Total Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>13}")
        write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>13}")
        write_line(summary_row("Total Neg. Entries", total_neg_entries_amt))
        write_line(summary_row("Total Gross Sales",  gross_sales))
        write_line(summary_row("Total Discounts",    total_disc))
        write_line(summary_row("Less Withdrawals:",  cash_withdrawals["total"] or 0))
        write_line(summary_row("Total Daily Sales",  net_sales))
        separator("=")
 
        # ── VAT summary ───────────────────────────────────────────────────────
        write_line(summary_row("Non-Vat:",       non_vat))
        write_line(summary_row("Vatable:",       vatable_sales))
        write_line(summary_row("V.A.T. Amount:", vat_amount))
  
        # ── Footer ────────────────────────────────────────────────────────────
        printer.write(b"\x1b\x61\x01")
        footers = _get_report_footers(terminal_config)

        if footers:
            for f in footers:
                # Default alignment
                align_cmd = b"\x1b\x61\x00"  # left

                if f.is_centered:
                    align_cmd = b"\x1b\x61\x01"  # center
                elif f.is_left_align:
                    align_cmd = b"\x1b\x61\x00"  # left

                printer.write(align_cmd)
                write_line(f.footer_text)

            # Always reset to left after all footers
            printer.write(b"\x1b\x61\x00")
            write_line("\n\n\n")
        else:
            write_line("Thank you!")
        printer.write(b"\x1b\x61\x00")


        # ── Feed & cut ────────────────────────────────────────────────────────
        printer.write(b"\x1d\x56\x00")
 
    finally:
        printer.close()
 
 
# =============================================================================
# VIEWS
# =============================================================================
 
@login_required
@require_open_session
def receipt_view(request):
    """Display receipt after payment and print it to the configured printer."""
    receipt = request.session.get("last_receipt")
    session = get_current_session_or_error(request)
    session = (
        POSSession.objects.select_related("opened_by")
        .prefetch_related("session_users__user")
        .get(id=session.id, status=POSSession.STATUS_OPEN)
    )
    current_operator = request.user
    if not receipt:
        return redirect("sales:pos_cashier")
 
    # Guard before any attribute access
    terminal_config = _get_terminal_config()
    if not terminal_config:
        print("❌ terminal_config is None")
        return redirect("sales:pos_cashier")
 
    setup_details = _get_store_details()
 
    tender_lines = receipt.get("tender_lines") or []
    if not tender_lines and receipt.get("tender"):
        tender_lines = [{
            "desc":    receipt["tender"],
            "amount":  receipt.get("amount_tendered", receipt["total"]),
            "is_cash": receipt.get("is_cash", False),
        }]
    
    context = {
        "store_name":       terminal_config.store_name or "OTTO Store",
        "transaction_no":   receipt["transaction_no"],
        "date":             receipt["date"],
        "time":             receipt["time"],
        "subtotal":         receipt.get("subtotal", receipt["total"]),
        "trans_disc_pct":   receipt.get("trans_disc_pct", "0"),
        "trans_disc_label": receipt.get("trans_disc_label", ""),
        "trans_disc_amt":   receipt.get("trans_disc_amt", "0"),
        "total":            receipt["total"],
        "tender":           receipt.get("tender", ""),
        "tender_lines":     tender_lines,
        "is_cash":          receipt.get("is_cash", False),
        "amount_tendered":  receipt.get("amount_tendered", ""),
        "change_amount":    receipt.get("change_amount", ""),
        "lines":            receipt["lines"],
        # "assisted_by":      receipt.get["salesperson"] or ""
        "headers":      list(terminal_config.headers.all().order_by("line_number")),
        "footers":      _get_customer_footers(terminal_config),
        "cashier_name": current_operator.get_full_name() or current_operator.username,
        "store_id":     session.store_id,
        "store_name":   terminal_config.store_name or "OTTO Store",
        "vat_exempt":    receipt.get("vat_exempt", ""),
        "vatable_amount": receipt.get("vatable_amount", ""),
        "vat_amount": receipt.get("vat_amount", ""),
        "vat_rate": "{:.0%}".format(float(receipt.get("vat_rate", "0.12") or "0.12")),

    }
 
    printer = None
    try:
        printer, _ = _get_printer(terminal_config)
        _print_receipt(printer, terminal_config, context, session)
    except NotImplementedError as e:
        print(f"❌ Printer not supported: {e}")
    except Exception as e:
        print(f"❌ Printer error: {e}")
    finally:
        if printer is not None:
            try:
                printer.close()
            except Exception:
                pass
 
    return render(request, "sales/receipt.html", context)
 
 
@login_required
@require_open_session
def z_reading_view(request):
    """Trigger a Z-Reading print for the current open session."""
    try:
        session = get_current_session_or_error(request)
        session = POSSession.objects.select_related("opened_by").get(
            id=session.id,
            status="open",
        )
    except POSSession.DoesNotExist:
        return JsonResponse({"error": "Open POS session not found."}, status=404)
    except POSSession.MultipleObjectsReturned:
        return JsonResponse({"error": "Multiple open sessions found."}, status=500)
 
    try:
        _do_print_z_reading(session)
    except NotImplementedError as e:
        return JsonResponse({"error": str(e)}, status=501)
    except Exception as e:
        print(f"❌ Z-Reading print error: {e}")
        return JsonResponse({"error": "Printer error. Check server logs."}, status=500)
 
    return JsonResponse({"status": "ok", "message": "Z-Reading printed."})


def _do_print_x_reading(session):
    """
    Print an X-Reading report for an already-resolved POSSession object.
    X-Reading = snapshot of current session totals WITHOUT closing/resetting.
    """
    terminal_config = _get_terminal_config()
    if not terminal_config:
        raise ValueError("Terminal configuration not found.")

    setup_details = _get_store_details()
    paper_width   = _get_paper_width(terminal_config)

    # ── Aggregate session data ─────────────────────────────────────────────────
    headers_qs = TransactionHeader.objects.filter(session=session)

    si_numbers = headers_qs.order_by("transaction_no").values_list("transaction_no", flat=True)
    beg_si = si_numbers.first() or "00000000"
    end_si = si_numbers.last()  or "00000000"

    void_line_items   = headers_qs.filter(transaction_type__in=[TRTYPE_VOID_ITEM, TRTYPE_VOID_ITEM_LEGACY]).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    void_transactions = headers_qs.filter(transaction_type__in=[TRTYPE_VOID_TRANS, TRTYPE_VOID_TRANS_LEGACY]).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    void_previous     = headers_qs.filter(transaction_type=TRTYPE_VOID_PREVIOUS).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    item_returns      = headers_qs.filter(return_code="R").aggregate(total=Sum("items__item_price_ext"),      count=Count("id"))
    cash_withdrawals  = Payment.objects.filter(header__session=session, pcode="CW").aggregate(total=Sum("amount"), count=Count("id"))

    total_neg = sum(filter(None, [
        void_line_items["total"], void_transactions["total"],
        void_previous["total"],   item_returns["total"],
        cash_withdrawals["total"],
    ]))

    sales_headers = headers_qs.exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL).exclude(return_code="R")

    gross_sales = (
        TransactionItem.objects.filter(header__in=sales_headers)
        .aggregate(total=Sum("item_price_ext"))["total"] or Decimal("0")
    )

    item_disc       = TransactionItem.objects.filter(header__in=sales_headers, discount_code="ID").aggregate(total=Sum("item_discount"), count=Count("id"))
    item_amt_disc   = TransactionItem.objects.filter(header__in=sales_headers, discount_code="IA").aggregate(total=Sum("item_discount"), count=Count("id"))
    senior_disc     = TransactionItem.objects.filter(header__in=sales_headers, discount_code="SC").aggregate(total=Sum("item_discount"), count=Count("id"))
    senior_amt_disc = TransactionItem.objects.filter(header__in=sales_headers, discount_code="SA").aggregate(total=Sum("item_discount"), count=Count("id"))

    total_disc = sum(filter(None, [
        item_disc["total"], item_amt_disc["total"],
        senior_disc["total"], senior_amt_disc["total"],
    ]))

    customer_count   = sales_headers.aggregate(total=Sum("customer_count"))["total"] or 0
    total_items_sold = TransactionItem.objects.filter(header__in=sales_headers).aggregate(total=Sum("item_qty"))["total"] or 0

    tender_breakdown = (
        Payment.objects.filter(header__in=sales_headers)
        .values("tender_desc", "pcode")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("tender_desc")
    )

    net_sales             = gross_sales - Decimal(str(total_disc))
    total_neg_entries_amt = Decimal(str(total_neg or 0))

    VAT_RATE      = Decimal("0.12")
    vatable_sales = net_sales / (1 + VAT_RATE)
    vat_amount    = net_sales - vatable_sales
    non_vat       = Decimal("0")

    now = datetime.datetime.now()

    # ── Open printer ───────────────────────────────────────────────────────────
    printer, _ = _get_printer(terminal_config)

    def write_line(text=""):
        printer.write((str(text) + "\n").encode("utf-8"))

    def separator(char="-"):
        write_line(char * paper_width)

    def fmt_count(val):
        try:
            return f"{int(val):>5}"
        except (TypeError, ValueError):
            return f"{'0':>5}"

    def neg_row(label, amount, count):
        return (
            f"     {label:<{paper_width - 21}}"
            f"{float(amount or 0):>10,.2f}"
            f"{int(count or 0):>5}"
        )

    def tendered(label, amount, count):
        return (
            f"{label:<{paper_width - 25}}"
            f"{float(amount or 0):>18,.2f}"
            f"{int(count or 0):>6}"
        )

    def summary_row(label, amount, count=None):
        amt_str = f"{float(amount or 0):>10,.2f}"
        if count is not None:
            return f"{label:<{paper_width - 14}}{amt_str}{int(count):>5}"
        return f"{label:<{paper_width - 13}}{amt_str}"

    def neg_gross(label, amount):
        return f"{label:<{paper_width - 16}}{float(amount or 0):>10,.2f}"

    def center(text):
        return text.center(paper_width)

    try:
        # ── Store header ───────────────────────────────────────────────────────
        printer.write(b"\x1b\x61\x01")
        db_headers = list(terminal_config.headers.all().order_by("line_number"))
        for h in db_headers:
            write_line(h.header_text)
        if not db_headers:
            write_line(setup_details.header01 or "OTTO Store")

        write_line(center("\n***** X-Reading Report *****\n"))

        printer.write(b"\x1b\x61\x00")

        # ── Terminal info ──────────────────────────────────────────────────────
        write_line(f"StoreId    : {session.store_id}")
        write_line(f"Terminal No: {session.terminal_id}")
        write_line(f"User Id    : {session.cashier.get_full_name() or session.cashier.username}")
        write_line(f"Date       : {session.business_date.strftime('%m/%d/%Y')}")
        write_line(f"Time       : {now.strftime('%I:%M:%S %p')}")
        write_line(f"\nBEG. SI    : {beg_si}")
        write_line(f"END. SI    : {end_si}\n")

        # ── Negative entries ───────────────────────────────────────────────────
        write_line("Negative Entries")
        write_line(neg_row("Void Line Item",   void_line_items["total"],   void_line_items["count"]))
        write_line(neg_row("Void Transaction", void_transactions["total"], void_transactions["count"]))
        write_line(neg_row("Void Previous",    void_previous["total"],     void_previous["count"]))
        write_line(neg_row("Item Returns",     item_returns["total"],      item_returns["count"]))
        write_line(neg_row("Cash Withdrawal",  cash_withdrawals["total"],  cash_withdrawals["count"]))
        separator()
        write_line(neg_gross("Total", total_neg_entries_amt))
        write_line("")

        # ── Gross sales & discounts ────────────────────────────────────────────
        write_line(neg_gross("GROSS SALES", gross_sales))
        write_line("\nLess:Discounts")
        write_line(neg_row("Item Disc.",     item_disc["total"],       item_disc["count"]))
        write_line(neg_row("Item Amt Disc.", item_amt_disc["total"],   item_amt_disc["count"]))
        write_line(neg_row("Senior % Disc.", senior_disc["total"],     senior_disc["count"]))
        write_line(neg_row("     Amt.Disc.", senior_amt_disc["total"], senior_amt_disc["count"]))
        separator()
        write_line(neg_gross("Total", total_disc))

        # ── Counts ────────────────────────────────────────────────────────────
        write_line(f"\n{'Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>15}")
        write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>15}")
        separator()

        # ── Tender breakdown ───────────────────────────────────────────────────
        for t in tender_breakdown:
            desc = (t["tender_desc"] or t["pcode"] or "CASH").upper()
            write_line(tendered(desc, t["total"], t["count"]))
        separator()
        write_line(neg_gross("NET SALES", net_sales))
        write_line("")
        separator()

        # ── VAT summary ────────────────────────────────────────────────────────
        write_line(summary_row("Non-Vat:",       non_vat))
        write_line(summary_row("Vatable:",       vatable_sales))
        write_line(summary_row("V.A.T. Amount:", vat_amount))
        separator("=")

        # ── Footer ─────────────────────────────────────────────────────────────
        printer.write(b"\x1b\x61\x01")
        footers = _get_report_footers(terminal_config)

        if footers:
            for f in footers:
                align_cmd = b"\x1b\x61\x01" if f.is_centered else b"\x1b\x61\x00"
                printer.write(align_cmd)
                write_line(f.footer_text)
            printer.write(b"\x1b\x61\x00")
        else:
            write_line("** THIS IS NOT AN OFFICIAL RECEIPT **")

        printer.write(b"\x1b\x61\x00")
        write_line("\n\n\n\n\n")

        # ── Feed & cut ─────────────────────────────────────────────────────────
        printer.write(b"\x1d\x56\x00")

    finally:
        printer.close()


# ── View ───────────────────────────────────────────────────────────────────────

@login_required
@require_open_session
@require_http_methods(["GET", "POST"])
def print_x_reading(request):
    """Print X-Reading for the current open session. Session stays open."""
    session = POSSession.objects.select_related("opened_by").filter(
        opened_by=request.user,
        store_id=STORE_ID,
        status="open",
    ).order_by("-opened_at").first()

    if not session:
        messages.error(request, "No active session found.")
        return redirect("sales:pos_cashier")

    try:
        _do_print_x_reading(session)
        messages.success(request, "X-Reading printed successfully.")
    except NotImplementedError as e:
        messages.error(request, f"Printer not supported: {e}")
    except Exception as e:
        messages.error(request, f"X-Reading print error: {e}")
        print(f"❌ X-Reading print error: {e}")

    return redirect("sales:pos_cashier")

# def _check_cloud_sync_status():




# def get_update_cloud(request): # For Temporary, I will only use this for the imported csv file. After the cloud sync is working, we can remove this and just call the check_cloud_sync_status() function in the relevant places. 
#     """
#     Utility view to trigger an update check for cloud sync status.
#     Not part of the regular flow, but can be called from the frontend or via curl.
#     """
#     try:
#         check_cloud_sync_status()
#         return JsonResponse({"status": "ok", "message": "Cloud sync status updated."})
#     except Exception as e:
#         print(f"❌ Cloud sync update error: {e}")
#         return JsonResponse({"status": "error", "message": str(e)}, status=500)


# Configure these in settings.py or TerminalSetup instead of hardcoding
CSV_ITEMS_PATH      = os.environ.get("CSV_ITEMS_PATH", "/data/exports/items.csv")
CSV_ITEMDTL_PATH    = os.environ.get("CSV_ITEMDTL_PATH", "/data/exports/itemdtl.csv")
CSV_ITEMSCOSTS_PATH = os.environ.get("CSV_ITEMSCOSTS_PATH", "/data/exports/itemscosts.csv")


@login_required
@require_http_methods(["POST"])          # cloud button should POST, not GET
def update_from_csv(request):
    """
    Truncates Item/ItemDetail tables and re-imports from the exported CSV files.
    Triggered by the cloud-download button in the cashier UI.
    """
    try:
        summary = import_products_from_csv(
            CSV_ITEMS_PATH,
            CSV_ITEMDTL_PATH,
            CSV_ITEMSCOSTS_PATH,
        )
        print(f"✅ CSV import summary: {summary}")
        return JsonResponse({
            "status": "ok",
            "message": (
                f"Import complete. "
                f"{summary['items_loaded']} items, "
                f"{summary['item_details_loaded']} variants, "
                f"{summary['costs_updated']} costs updated."
            ),
            **summary,
        })
    except FileNotFoundError as e:
        return JsonResponse({"status": "error", "message": f"CSV file not found: {e}"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)