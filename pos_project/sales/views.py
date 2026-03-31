"""
POS Cashier views: login, cashier screen, cart operations.
"""

import datetime
import django.utils.timezone as timezone
from decimal import Decimal
from pyexpat.errors import messages
from django.http import JsonResponse

from django.db import models
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from users.models import POSSession

from .decorators import require_open_session
from .models import Item, ItemDetail, TempTransaction, TerminalConfiguration, TerminalReceiptFooter, TransactionHeader, POSTransCounter, Tender, TerminalSetup, Color, Size, Payment, TransactionItem
from .services import get_business_date

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


def _get_user_id(request):
    """Return user_id for POS (Django username or ClarionUser id)."""
    return request.user.username[:10] if request.user.is_authenticated else ""


#    To be checked if we want to keep these as part of the user model instead of moving to TerminalSetup or TerminalConfiguration, which would allow for more flexible assignment of terminals to users in the future. For now, these are used as the default store_id and terminal_id for session tracking and transaction logging, but they could be overridden by fields in the POSSession model or by related TerminalSetup/Configuration records.
# def _get_store_id(request):
#     """Get store_id from logged-in user, fallback to default."""
#     if request.user.is_authenticated:
#         return request.user.store_id or "001"
#     return "001"


# def _get_terminal_id(request):
#     """Get terminal_id from logged-in user, fallback to default."""
#     if request.user.is_authenticated:
#         return request.user.terminal_id or "001"
#     return "001"

# ----------------------------------------------------------------------------
# Getting the current session's store_id and terminal_id from the POSSession model instead of the user model allows for more flexible assignment of terminals to users and better tracking of sessions across different terminals. This way, the store_id and terminal_id are tied to the actual POS session rather than the user account, which can be useful in scenarios where users may operate multiple terminals or when terminals are shared among users. The helper functions can be updated to retrieve this information from the current open session for the logged-in user, ensuring that all operations are correctly associated with the active session's store and terminal.
# ----------------------------------------------------------------------------
def get_current_session(request):
    """Return the current open POS session of the logged-in user."""
    if not request.user.is_authenticated:
        return None

    return POSSession.objects.filter(
        cashier=request.user,
        status=POSSession.STATUS_OPEN
    ).order_by("-opened_at").first()


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
        session = POSSession.objects.select_related("cashier").get(
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

# ---------------------------------------------------------------------------

def _get_next_transaction_no():
    """Get and increment the next transaction number."""
    try:
        row = POSTransCounter.objects.first()
        if row:
            trans_no = row.transaction_no
            try:
                n = int(trans_no)
                next_no = str(n + 1).zfill(8)
            except ValueError:
                next_no = "00000001"
            row.transaction_no = next_no
            row.save()
            return next_no
    except Exception:
        pass
    return "00000001"

# ---------------------------------------------------------------------------
# Open session view
# ---------------------------------------------------------------------------

@login_required
def open_session(request):
    user = request.user

    # Prevent multiple open sessions
    if POSSession.objects.filter(cashier=user, status="open").exists():
        messages.info(request, "You already have an open session.")
        return redirect("sales:pos_cashier")

    if request.method == "POST":
        opening_cash = request.POST.get("opening_cash")

        # Validate opening cash
        try:
            opening_cash = float(opening_cash) # I CHANGE ITO ACCORDING SA EXPECTED AMOUNT 
        except (TypeError, ValueError):
            messages.error(request, "Invalid opening cash amount.")
            return redirect("sales:open_session")

        # Create new POS session
        POSSession.objects.create(
            cashier=user,
            terminal_id="001",
            store_id="001",
            business_date=datetime.date.today(),
            opening_cash=opening_cash,
            status="open"
        )

        # messages.success(request, "POS session opened successfully.")
        return redirect("sales:pos_cashier")

    return render(request, "sales/open_session.html")


@login_required
@require_open_session
@require_http_methods(["GET"])
def to_close_session_details(request):
    user = request.user
    session = POSSession.objects.filter(
        cashier=user,
        store_id=STORE_ID,
        status="open",
    ).order_by("-opened_at").first()

    if not session:
        return JsonResponse({"error": "No open session found."}, status=400)

    return JsonResponse({
        "opening_cash": float(session.opening_cash),
    })

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
    }
    return render(request, "sales/cashier.html", context)


# ---------------------------------------------------------------------------
# Cart API (HTMX / JSON)
# ---------------------------------------------------------------------------

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
        item_code = item_detail.icode
    else:
        item = Item.objects.get(icode=barcode)
        desc = item.short_desc or item.long_desc or item.icode
        price = item.price
        size = item.size or ""
        color = item.color or ""
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

    if total <= 0:
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
    """Parse tender_entries JSON from POST. Returns list of (pcode, amount) or empty."""
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
            if pcode and amt > 0:
                entries.append((pcode, amt))
        return entries
    except (json.JSONDecodeError, TypeError):
        return []


@login_required
@require_open_session
@require_http_methods(["POST"])
def payment_complete(request):
    """Complete payment with tender entries. Supports multiple tenders. Only completes when total tendered >= amount due."""
    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    tender_entries = _parse_tender_entries(request)
    current_session = get_current_session(request)

    if not tender_entries:
        return redirect("sales:pay")

    cart_lines = TempTransaction.objects.filter(
        user_id=user_id,
        terminal_id=TERMINAL_ID,
        store_id=STORE_ID,
        transaction_no=trans_no,
    ).order_by("rec_ctr")

    if not cart_lines.exists():
        return redirect("sales:pos_cashier")

    trans_disc = _get_trans_disc(request)
    subtotal, trans_disc_amt, total = _compute_totals(cart_lines, trans_disc)

    total_tendered = sum(amt for _, amt in tender_entries)
    if total_tendered < total:
        return redirect("sales:pay")

    now = datetime.datetime.now()
    try:
        biz_date = get_business_date(STORE_ID, TERMINAL_ID, now)
    except Exception:
        biz_date = now.date()

    # --- Build tender summary ---
    tender_lines = []
    total_cash = Decimal("0")
    for pcode, amt in tender_entries:
        tender = Tender.objects.filter(pcode=pcode).first()
        desc = tender.description if tender else pcode
        is_cash = bool(tender and tender.pchange == "Y")
        tender_lines.append({"desc": desc, "amount": str(amt), "is_cash": is_cash})
        if is_cash:
            total_cash += amt

    change_amount = max(Decimal("0"), total_tendered - total) if total_cash > 0 else Decimal("0")
    tender_display = ", ".join(f"{t['desc']} ₱{t['amount']}" for t in tender_lines)

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
        for line in cart_lines
    ])

    # --- Create one Payment per tender entry ---
    Payment.objects.bulk_create([
        Payment(
            header=header,
            pcode=pcode,
            amount=amt,
            tender_desc=next(
                (t["desc"] for t in tender_lines if t["amount"] == str(amt)), pcode
            ),
            payment_reference="",
        )
        for pcode, amt in tender_entries
    ])

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
        "is_cash": any(t["is_cash"] for t in tender_lines),
        "amount_tendered": str(total_tendered),
        "change_amount": str(change_amount),
        "lines": [
            {
                "description": line.item_description or "",
                "qty": str(line.item_qty),
                "price": str(line.item_price or 0),
                "gross": str(line.item_gross),
                "disc_pct": line.disc_pct,
                "disc_total": str(line.item_disc_total),
                "ext": str(line.item_price_ext or 0),
                "size": line.item_size or "",
                "color": line.item_color or "",
            }
            for line in cart_lines
        ],
    }

    # --- Clear cart, advance transaction number ---
    cart_lines.delete()
    request.session["pos_trans_no"] = _get_next_transaction_no()
    _clear_trans_disc(request)

    return redirect("sales:receipt")




# @login_required
# @require_open_session
# def _print_reading(request):
#     """
#     Print a Z-Reading report for the given POSSession.
#     Uses serial port from TerminalConfiguration, same as receipt printing.
#     """


#     # =============================
#     # SETUP & CONFIG
#     # =============================
#     setup_details = _get_store_details()

#     terminal_config = TerminalConfiguration.objects.prefetch_related(
#         'headers',
#         models.Prefetch(
#             'footers',
#             queryset=TerminalReceiptFooter.objects.filter(
#                 footer_type__in=["customer", "both"]
#             ).order_by("line_number"),
#             to_attr="customer_footers"
#         ),
#         'ports',
#         'display_codes'
#     ).filter(
#         store_id=STORE_ID,
#         terminal_id=TERMINAL_ID
#     ).first()

#     if not terminal_config:
#         print("terminal_config is None")
#         return

#     try:
#         session = get_current_session_or_error(request)

#         _print_reading(session.id)
#         session = POSSession.objects.select_related('cashier').get(
#             id=session.id,
#             status="open",
#         )
#     except POSSession.DoesNotExist:
#         return JsonResponse(
#             {"error": "Open POS session not found for the provided session ID."},
#             status=404,
#         )
#     except POSSession.MultipleObjectsReturned:
#         return JsonResponse(
#             {"error": "Multiple open POS sessions found for the provided session ID."},
#             status=500,
#         )
#     print(f"Generating Z-Reading for session {session.id} (Cashier: {session.cashier.username})")
#     # All transaction headers for this session
#     headers_qs = TransactionHeader.objects.filter(session=session)

#     # SI range
#     si_numbers = headers_qs.order_by('transaction_no').values_list('transaction_no', flat=True)
#     beg_si = si_numbers.first() or "00000000"
#     end_si = si_numbers.last() or "00000000"

#     # Negative entries — based on transaction_type or return_code conventions
#     # Adjust field values to match your actual data ('V', 'R', etc.)
#     void_line_items = headers_qs.filter(transaction_type='L').aggregate(
#         total=Sum('items__item_price_ext'), count=Count('id')
#     )
#     void_transactions = headers_qs.filter(transaction_type='V').aggregate(
#         total=Sum('items__item_price_ext'), count=Count('id')
#     )
#     void_previous = headers_qs.filter(transaction_type='P').aggregate(
#         total=Sum('items__item_price_ext'), count=Count('id')
#     )
#     item_returns = headers_qs.filter(return_code='R').aggregate(
#         total=Sum('items__item_price_ext'), count=Count('id')
#     )

#     # Cash withdrawals — adjust pcode to your actual cash withdrawal code
#     cash_withdrawals = Payment.objects.filter(
#         header__session=session, pcode='CW'
#     ).aggregate(total=Sum('amount'), count=Count('id'))

#     total_neg = sum(filter(None, [
#         void_line_items['total'],
#         void_transactions['total'],
#         void_previous['total'],
#         item_returns['total'],
#         cash_withdrawals['total'],
#     ]))

#     # Sales transactions only (exclude voids/returns for gross sales)
#     sales_headers = headers_qs.exclude(
#         transaction_type__in=['V', 'L', 'P']
#     ).exclude(return_code='R')

#     gross_sales = TransactionItem.objects.filter(
#         header__in=sales_headers
#     ).aggregate(total=Sum('item_price_ext'))['total'] or Decimal('0')

#     # Discounts
#     item_disc = TransactionItem.objects.filter(
#         header__in=sales_headers,
#         discount_code__in=['ID']  # adjust to your item discount code
#     ).aggregate(total=Sum('item_discount'), count=Count('id'))

#     item_amt_disc = TransactionItem.objects.filter(
#         header__in=sales_headers,
#         discount_code__in=['IA']  # adjust to your item amount discount code
#     ).aggregate(total=Sum('item_discount'), count=Count('id'))

#     senior_disc = TransactionItem.objects.filter(
#         header__in=sales_headers,
#         discount_code__in=['SC']  # adjust to your senior discount code
#     ).aggregate(total=Sum('item_discount'), count=Count('id'))

#     senior_amt_disc = TransactionItem.objects.filter(
#         header__in=sales_headers,
#         discount_code__in=['SA']
#     ).aggregate(total=Sum('item_discount'), count=Count('id'))

#     total_disc = sum(filter(None, [
#         item_disc['total'],
#         item_amt_disc['total'],
#         senior_disc['total'],
#         senior_amt_disc['total'],
#     ]))

#     # Customer count & item count
#     customer_count = sales_headers.aggregate(
#         total=Sum('customer_count')
#     )['total'] or 0

#     total_items_sold = TransactionItem.objects.filter(
#         header__in=sales_headers
#     ).aggregate(total=Sum('item_qty'))['total'] or 0

#     # Tender breakdown — group by tender_desc
#     tender_breakdown = Payment.objects.filter(
#         header__in=sales_headers
#     ).values('tender_desc', 'pcode').annotate(
#         total=Sum('amount'),
#         count=Count('id')
#     ).order_by('tender_desc')

#     # GC Sales (Gift Certificate) — adjust pcode as needed
#     gc_sales = Payment.objects.filter(
#         header__in=sales_headers, pcode='GC'
#     ).aggregate(total=Sum('amount'), count=Count('id'))

#     net_sales = gross_sales - Decimal(str(total_disc))

#     # Grand totals (you may pull these from a separate GrandTotal model)
#     # Replace with actual old/new grand total logic
#     old_grand_total = Decimal('75198919.10')  # TODO: fetch from your GrandTotal model
#     new_grand_total = old_grand_total + gross_sales

#     total_neg_entries_amt = Decimal(str(total_neg or 0))

#     # VAT computation (12% VAT inclusive)
#     VAT_RATE = Decimal('0.12')
#     vatable_sales = net_sales / (1 + VAT_RATE)
#     vat_amount = net_sales - vatable_sales
#     non_vat = Decimal('0')  # adjust if you track non-vat sales separately

#     # =============================
#     # PORT CONFIG
#     # =============================
#     ports = {p.port_type: p for p in terminal_config.ports.all()}
#     display_codes = {d.code_group: d for d in terminal_config.display_codes.all()}

#     paper_width = 40
#     if "PW" in display_codes and display_codes["PW"].code_value:
#         try:
#             paper_width = int(display_codes["PW"].code_value)
#         except:
#             pass

#     printer_port = ports.get("PRINTER")
#     if not printer_port:
#         raise Exception("Printer port not configured")

#     printer = serial.Serial(
#         port=printer_port.port_name,
#         baudrate=9600,
#         bytesize=8,
#         parity='N',
#         stopbits=1,
#         timeout=1
#     )
#     time.sleep(1)

#     # =============================
#     # HELPERS
#     # =============================
#     def write_line(text=""):
#         printer.write((text + "\n").encode("utf-8"))

#     def separator(char="-"):
#         write_line(char * paper_width)

#     def fmt_money(val):
#         try:
#             return f"{float(val):>15,.2f}"
#         except:
#             return f"{'0.00':>15}"

#     def fmt_count(val):
#         try:
#             return f"{int(val):>5}"
#         except:
#             return f"{'0':>5}"

#     def neg_row(label, amount, count):
#         """
#         Format:  '     Label          0.00    0'
#         Label is indented 5 spaces, amount right-aligned, count right-aligned.
#         """
#         label_col = f"     {label}"
#         amt_str   = f"{float(amount):>10,.2f}"
#         cnt_str   = f"{int(count):>5}"
#         return f"{label_col:<{paper_width - 16}}{amt_str}{cnt_str}"

#     def summary_row(label, amount, count=None):
#         """
#         Format:  'LABEL               10,432.60    7'
#         or       'LABEL               10,432.60'  (no count)
#         """
#         amt_str = f"{float(amount):>10,.2f}"
#         if count is not None:
#             cnt_str = f"{int(count):>5}"
#             return f"{label:<{paper_width - 16}}{amt_str}{cnt_str}"
#         else:
#             return f"{label:<{paper_width - 11}}{amt_str}"

#     def center(text):
#         return text.center(paper_width)

#     # =============================
#     # PRINT HEADER (DB)
#     # =============================
#     printer.write(b'\x1b\x61\x01')  # center align
#     headers = terminal_config.headers.all().order_by("line_number")
#     if headers.exists():
#         for h in headers:
#             write_line(h.header_text)
#     else:
#         write_line(setup_details.header01 or "OTTO Store")

#     write_line(center("***** Z-Reading Report *****"))
#     printer.write(b'\x1b\x61\x00')  # left align

#     # =============================
#     # TERMINAL INFO
#     # =============================
#     write_line(f"StoreId    : {session.store_id}")
#     write_line(f"Terminal No: {session.terminal_id}")
#     write_line(f"User Id    : {session.cashier.get_full_name() or session.cashier.username}")
#     write_line(f"Date       : {session.business_date.strftime('%m/%d/%Y')}")
#     write_line(f"BEG. SI    : {beg_si}")
#     write_line(f"END. SI    : {end_si}")

#     # =============================
#     # NEGATIVE ENTRIES
#     # =============================
#     write_line("Negative Entries")
#     write_line(neg_row("Void Line Item",   void_line_items['total']  or 0, void_line_items['count']  or 0))
#     write_line(neg_row("Void Transaction", void_transactions['total'] or 0, void_transactions['count'] or 0))
#     write_line(neg_row("Void Previous",    void_previous['total']    or 0, void_previous['count']    or 0))
#     write_line(neg_row("Item Returns",     item_returns['total']     or 0, item_returns['count']     or 0))
#     write_line(neg_row("Cash Withdrawal",  cash_withdrawals['total'] or 0, cash_withdrawals['count'] or 0))
#     separator()
#     write_line(summary_row("Total", total_neg_entries_amt))

#     # =============================
#     # GROSS SALES & DISCOUNTS
#     # =============================
#     write_line(summary_row("GROSS SALES", gross_sales))
#     write_line("Less:Discounts")
#     write_line(neg_row("Item Disc.",     item_disc['total']     or 0, item_disc['count']     or 0))
#     write_line(neg_row("Item Amt Disc.", item_amt_disc['total'] or 0, item_amt_disc['count'] or 0))
#     write_line(neg_row("Senior % Disc.", senior_disc['total']   or 0, senior_disc['count']   or 0))
#     write_line(neg_row("     Amt.Disc.", senior_amt_disc['total'] or 0, senior_amt_disc['count'] or 0))
#     separator()
#     write_line(summary_row("Total", total_disc))

#     # =============================
#     # COUNTS
#     # =============================
#     write_line(f"{'Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>16}")
#     write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>16}")
#     separator()

#     # =============================
#     # TENDER BREAKDOWN
#     # =============================
#     for t in tender_breakdown:
#         desc  = (t['tender_desc'] or t['pcode'] or "CASH").upper()
#         total = t['total'] or 0
#         count = t['count'] or 0
#         write_line(neg_row(desc, total, count))  # reuse neg_row layout

#     write_line(neg_row("GC SALES", gc_sales['total'] or 0, gc_sales['count'] or 0))
#     separator()
#     write_line(summary_row("NET SALES", net_sales))
#     separator()

#     # =============================
#     # TERMINAL SUMMARY
#     # =============================
#     printer.write(b'\x1b\x61\x01')
#     write_line(center("Terminal Summary Total"))
#     printer.write(b'\x1b\x61\x00')
#     separator()
#     separator()
#     write_line(summary_row("OLD GRAND TOTAL", old_grand_total))
#     write_line(summary_row("NEW GRAND TOTAL", new_grand_total))
#     separator()
#     write_line(f"{'Total Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>16}")
#     write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>16}")
#     write_line(summary_row("Total Neg. Entries", total_neg_entries_amt))
#     write_line(summary_row("Total Gross Sales",  gross_sales))
#     write_line(summary_row("Total Discounts",    total_disc))
#     write_line(summary_row("Less Withdrawals:",  cash_withdrawals['total'] or 0))
#     write_line(summary_row("Total Daily Sales",  net_sales))
#     separator("=")

#     # =============================
#     # VAT SUMMARY
#     # =============================
#     write_line(summary_row("Non-Vat:", non_vat))
#     write_line(summary_row("Vatable:", vatable_sales))
#     write_line(summary_row("V.A.T. Amount:", vat_amount))

#     # =============================
#     # FOOTER (DB)
#     # =============================
#     separator()
#     printer.write(b'\x1b\x61\x01')
#     footers = terminal_config.customer_footers
#     if footers:
#         for f in footers:
#             write_line(f.footer_text)
#     else:
#         write_line("Thank you!")
#     printer.write(b'\x1b\x61\x00')

#     # =============================
#     # FEED & CUT
#     # =============================
#     write_line("\n" * 5)
#     printer.write(b'\x1d\x56\x00')
#     printer.close()


# def _open_printer(printer_port):
#     """
#     Open a printer connection based on the port's connection_type.
#     Returns an open connection object with a .write(bytes) method.
#     Raises ValueError for unsupported or misconfigured connection types.
#     """
#     connection_type = printer_port.connection_type
 
#     if connection_type == "SERIAL":
#         if not printer_port.port_name:
#             raise ValueError("Serial printer port_name is not configured.")
#         conn = serial.Serial(
#             port=printer_port.port_name,
#             baudrate=printer_port.baudrate or 9600,
#             bytesize=8,
#             parity="N",
#             stopbits=1,
#             timeout=1,
#         )
#         time.sleep(1)
#         return conn
 
#     elif connection_type == "USB":
#         # USB serial — treat like serial but without baudrate requirement
#         if not printer_port.port_name:
#             raise ValueError("USB printer port_name is not configured.")
#         conn = serial.Serial(
#             port=printer_port.port_name,
#             baudrate=printer_port.baudrate or 9600,
#             bytesize=8,
#             parity="N",
#             stopbits=1,
#             timeout=1,
#         )
#         time.sleep(1)
#         return conn
 
#     elif connection_type == "NETWORK":
#         if not printer_port.ip_address or not printer_port.port_no:
#             raise ValueError("Network printer ip_address and port_no must be configured.")
#         conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         conn.connect((printer_port.ip_address, printer_port.port_no))
#         conn.settimeout(5)
#         # Wrap socket so it exposes a .write() and .close() interface
#         return _SocketPrinterWrapper(conn)
 
#     elif connection_type == "WINDOWS":
#         # Windows GDI / raw print — not yet implemented
#         raise NotImplementedError(
#             f"Windows printer support is not yet implemented "
#             f"(port: {printer_port.printer_name!r})."
#         )
 
#     else:
#         raise ValueError(f"Unsupported printer connection_type: {connection_type!r}")
 
 
# class _SocketPrinterWrapper:
#     """Thin wrapper so a network socket exposes the same .write()/.close() API as serial.Serial."""
 
#     def __init__(self, sock):
#         self._sock = sock
 
#     def write(self, data: bytes):
#         self._sock.sendall(data)
 
#     def close(self):
#         self._sock.close()
 
 
# def _print_receipt(printer, terminal_config, context):
#     """
#     Send the full receipt byte-stream to the already-open printer connection.
#     Isolated from the view so it can be tested or reused independently.
#     """
#     ports = {p.port_type: p for p in terminal_config.ports.all()}
#     display_codes = {d.code_group: d for d in terminal_config.display_codes.all()}
 
#     # ── Paper width ──────────────────────────────────────────────────────────
#     paper_width = 40
#     if "PW" in display_codes and display_codes["PW"].code_value:
#         try:
#             paper_width = int(display_codes["PW"].code_value)
#         except ValueError:
#             pass
 
#     # ── Column sizes ─────────────────────────────────────────────────────────
#     if paper_width >= 48:
#         LEFT_WIDTH = 32
#     else:
#         LEFT_WIDTH = 22
#     RIGHT_WIDTH = paper_width - LEFT_WIDTH
 
#     # ── Helpers ──────────────────────────────────────────────────────────────
#     def write_line(text=""):
#         printer.write((text + "\n").encode("utf-8"))
 
#     def separator():
#         write_line("-" * paper_width)
 
#     def align_lr(left="", right=""):
#         left, right = str(left), str(right)
#         return left.ljust(paper_width - len(right)) + right
 
#     def item_line(qty, price, total):
#         return f"{qty} x {price}".ljust(LEFT_WIDTH) + f"{total}".rjust(RIGHT_WIDTH)
 
#     def format_money(val):
#         try:
#             return f"{float(val):,.2f}"
#         except (TypeError, ValueError):
#             return str(val)
 
#     def format_qty(val):
#         try:
#             return f"{float(val):,.0f}"
#         except (TypeError, ValueError):
#             return str(val)
 
#     # ── Header ───────────────────────────────────────────────────────────────
#     printer.write(b"\x1b\x61\x01")  # center
#     headers = terminal_config.headers.all().order_by("line_number")
#     if headers.exists():
#         for h in headers:
#             write_line(h.header_text)
#     else:
#         write_line("OTTO Store")
 
#     printer.write(b"\x1b\x61\x00")  # left
#     write_line(f"Receipt #: {context['transaction_no']}")
#     separator()
 
#     # ── Items ─────────────────────────────────────────────────────────────────
#     for line in context["lines"]:
#         desc = line.get("description", "")[:paper_width]
#         qty = format_qty(line.get("qty"))
#         price = format_money(line.get("price"))
#         total = format_money(line.get("ext"))
 
#         write_line(desc)
#         write_line(item_line(qty, price, total))
 
#         if line.get("disc_pct"):
#             write_line(f"  {line['disc_pct']}% - {format_money(line.get('disc_total'))}")
 
#     # ── Transaction discount ──────────────────────────────────────────────────
#     if context["trans_disc_amt"] not in ("0", "0.0000", None, ""):
#         separator()
#         write_line(align_lr("Subtotal", format_money(context["subtotal"])))
#         write_line(f"{context['trans_disc_label']} ({context['trans_disc_pct']}%)")
#         write_line(align_lr("Discount", f"-{format_money(context['trans_disc_amt'])}"))
 
#     # ── Total ─────────────────────────────────────────────────────────────────
#     separator()
#     printer.write(b"\x1b\x45\x01")  # bold on
#     write_line(align_lr("TOTAL", format_money(context["total"])))
#     printer.write(b"\x1b\x45\x00")  # bold off
#     separator()
 
#     # ── Tender lines ──────────────────────────────────────────────────────────
#     for t in context["tender_lines"]:
#         write_line(align_lr(t["desc"], format_money(t["amount"])))
 
#     if context["amount_tendered"]:
#         write_line(align_lr("Tendered", format_money(context["amount_tendered"])))
 
#     if context["is_cash"] and context["change_amount"] not in ("", "0", "0.0000"):
#         printer.write(b"\x1b\x45\x01")
#         write_line(align_lr("CHANGE", format_money(context["change_amount"])))
#         printer.write(b"\x1b\x45\x00")
 
#     # ── Footer ────────────────────────────────────────────────────────────────
#     separator()
#     printer.write(b"\x1b\x61\x01")  # center
 
#     # FIX: customer_footers is a plain list (set via to_attr), not a queryset
#     footers = terminal_config.footers.all()
#     if footers:
#         for f in sorted(footers, key=lambda x: x.line_number):
#             write_line(f.footer_text)
#     else:
#         write_line("Thank you for your purchase!")
#     # footers = terminal_config.footers.all().order_by("line_number")
#     # if footers.exists():
#     #     for f in footers:
#     #         write_line(f.footer_text)
#     # else:
#     #     write_line("Thank you for your purchase!")
 
#     printer.write(b"\x1b\x61\x00")  # left
 
#     # ── Cash drawer pulse ─────────────────────────────────────────────────────
#     drawer_port = ports.get("DRAWER")
#     if drawer_port:
#         try:
#             printer.write(b"\x1b\x70\x00\x19\xfa")
#         except Exception as e:
#             print(f"⚠️  Cash drawer pulse failed: {e}")
 
#     # ── Feed & cut ────────────────────────────────────────────────────────────
#     write_line("\n" * 5)
#     printer.write(b"\x1d\x56\x00")
 
 
# @login_required
# @require_open_session
# def receipt_view(request):
#     """Display receipt after payment. Data comes from session."""

#     receipt = request.session.get("last_receipt")
#     if not receipt:
#         return redirect("sales:pos_cashier")
 
#     setup_details = _get_store_details()
 
#     terminal_config = (
#         TerminalConfiguration.objects.prefetch_related(
#             "headers",
#             models.Prefetch(
#                 "footers",
#                 queryset=TerminalReceiptFooter.objects.filter(
#                     footer_type__in=["customer", "both"]
#                 ).order_by("line_number"),
#                 to_attr="customer_footers",  # resolves to a plain list, not a queryset
#             ),
#             # "footers",
#             "ports",
#             "display_codes",
#         )
#         .filter(store_id=STORE_ID, terminal_id=TERMINAL_ID)
#         .first()
#     )
#      # =============================
#     # PORT CONFIG
#     # =============================
#     ports = {p.port_type: p for p in terminal_config.ports.all()}
#     display_codes = {d.code_group: d for d in terminal_config.display_codes.all()}

#     # Print all TerminalConfiguration details
#     print("\n=== TERMINAL CONFIGURATION ===")
#     print(f"ID: {terminal_config.id}")
#     print(f"Store ID: {terminal_config.store_id}")
#     print(f"Terminal ID: {terminal_config.terminal_id}")
#     # print(f"Created At: {terminal_config.created_at}")
#     # print(f"Updated At: {terminal_config.updated_at}")
    
#     # Print all headers
#     print("\n=== HEADERS ===")
#     headers = terminal_config.headers.all()
#     for h in headers:
#         print(f"  ID: {h.id}, Line: {h.line_number}, Text: {h.header_text}")
    
#     # Print all footers
#     print("\n=== FOOTERS ===")
#     footers = terminal_config.footers.all()
#     for f in footers:
#         print(f"  ID: {f.id}, Type: {f.footer_type}, Line: {f.line_number}, Text: {f.footer_text}")
    
#     # Print customer footers (from prefetch)
#     print("\n=== CUSTOMER FOOTERS (prefetched) ===")
#     customer_footers = terminal_config.footers.all()
#     if customer_footers:
#         for cf in customer_footers:
#             print(f"  ID: {cf.id}, Type: {cf.footer_type}, Line: {cf.line_number}, Text: {cf.footer_text}")
#     else:
#         print("  No customer footers found")
    
#     # Print all ports
#     print("\n=== ALL PORTS ===")
#     for port_type, port_obj in ports.items():
#         print(f"\n  Port Type: {port_type}")
#         print(f"    ID: {port_obj.id}")
#         print(f"    Port Name: {port_obj.port_name}")
#         print(f"    Connection Type: {port_obj.connection_type}")
#         print(f"    Baudrate: {port_obj.baudrate}")
#         print(f"    IP Address: {port_obj.ip_address}")
#         print(f"    Port No: {port_obj.port_no}")
#         print(f"    Printer Name: {port_obj.printer_name}")
    
#     # Print display codes
#     print("\n=== DISPLAY CODES ===")
#     for code_group, code_obj in display_codes.items():
#         print(f"\n  Code Group: {code_group}")
#         print(f"    ID: {code_obj.id}")
#         print(f"    Code Value: {code_obj.code_value}")
#         print(f"    Code Description: {code_obj.code_description}")
    
#     # Print printer port details
#     print("\n=== PRINTER PORT DETAIL ===")
#     printer_port = ports.get("PRINTER")
#     if printer_port:
#         print(f"  Port Type: PRINTER")
#         print(f"  Port Name: {printer_port.port_name}")
#         print(f"  Connection Type: {printer_port.connection_type}")
#         print(f"  Baudrate: {printer_port.baudrate}")
#         print(f"  IP Address: {printer_port.ip_address}")
#         print(f"  Port No: {printer_port.port_no}")
#         print(f"  Printer Name: {printer_port.printer_name}")
#     else:
#         print("  ❌ No PRINTER port found!")
    
#     print("\n")

#     paper_width = 40
#     if "PW" in display_codes and display_codes["PW"].code_value:
#         try:
#             paper_width = int(display_codes["PW"].code_value)
#         except:
#             pass

#     if not printer_port:
#         raise Exception("Printer port not configured")
    
#     if not terminal_config:
#         # FIX: must return an HttpResponse, not bare None
#         print("terminal_config is None")
#         return redirect("sales:pos_cashier")
 
#     # ── Normalise tender lines ────────────────────────────────────────────────
#     tender_lines = receipt.get("tender_lines") or []
#     if not tender_lines and receipt.get("tender"):
#         tender_lines = [
#             {
#                 "desc": receipt["tender"],
#                 "amount": receipt.get("amount_tendered", receipt["total"]),
#                 "is_cash": receipt.get("is_cash", False),
#             }
#         ]
 
#     context = {
#         "store_name": setup_details.header01 or "OTTO Store",
#         "transaction_no": receipt["transaction_no"],
#         "date": receipt["date"],
#         "time": receipt["time"],
#         "subtotal": receipt.get("subtotal", receipt["total"]),
#         "trans_disc_pct": receipt.get("trans_disc_pct", "0"),
#         "trans_disc_label": receipt.get("trans_disc_label", ""),
#         "trans_disc_amt": receipt.get("trans_disc_amt", "0"),
#         "total": receipt["total"],
#         "tender": receipt.get("tender", ""),
#         "tender_lines": tender_lines,
#         "is_cash": receipt.get("is_cash", False),
#         "amount_tendered": receipt.get("amount_tendered", ""),
#         "change_amount": receipt.get("change_amount", ""),
#         "lines": receipt["lines"],
#     }
 
 
        
#     _print_reading(request)

#     return render(request, "sales/receipt.html", context)


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
                    "price": str(v.price or item.price),
                })
        else:
            results.append({
                "barcode": item.icode,
                "code": item.icode,
                "description": item.short_desc or item.long_desc,
                "size": item.size or "",
                "color": item.color or "",
                "price": str(item.price),
            })

    return JsonResponse({"results": results})


# ---------------------------------------------------------------------------
# Close session view
# ---------------------------------------------------------------------------

@login_required
@require_open_session
@require_http_methods(["POST"])
def close_session(request):
    user = request.user

    # Find the active cashier session for this user + terminal + store
    session = POSSession.objects.filter(
        cashier=user,
        store_id=STORE_ID,       # your existing constant
        status="open",
    ).order_by("-opened_at").first()

    if not session:
        messages.error(request, "No active session found to close.")
        return redirect("sales:pos_cashier")

    # --- Parse POST values ---
    def parse_decimal(val, default=0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    closing_cash  = parse_decimal(request.POST.get("closing_cash"))
    expected_cash = parse_decimal(request.POST.get("expected_cash"))
    cash_variance = parse_decimal(request.POST.get("cash_variance"))
    notes         = request.POST.get("notes", "").strip()
    print(session)
    print(closing_cash)
    print(expected_cash)
    print(cash_variance)
    if closing_cash < 0:
        messages.error(request, "Closing cash cannot be negative.")
        return redirect("sales:pos_cashier")

    # --- Update and close the session ---
    session.closing_cash  = closing_cash
    session.expected_cash = expected_cash
    session.cash_variance = cash_variance
    session.notes         = notes or None
    session.closed_at   = timezone.now()
    session.status = "closed"
    session.save(update_fields=[
        "closing_cash", 
        # "expected_cash",
        # "cash_variance",
        # "notes",
        "closed_at", 
        "status", 
        # "updated_at",
    ])

    # --- Audit trail entry ---
    # AuditTrail.objects.create(
    #     user_id=user.pk,
    #     username=user.username,
    #     action_type="LOGOUT",
    #     action_description=(
    #         f"Session closed. Closing cash: {closing_cash:.2f}, "
    #         f"Expected: {expected_cash:.2f}, Variance: {cash_variance:.2f}"
    #     ),
    #     table_name="cashier_sessions",
    #     record_id=str(session.pk),
    #     new_values={
    #         "closing_cash":  closing_cash,
    #         "expected_cash": expected_cash,
    #         "cash_variance": cash_variance,
    #         "session_status": "closed",
    #     },
    #     terminal_id=TERMINAL_ID,
    #     store_id=STORE_ID,
    # )

    # Clear session keys set during this POS session
    for key in ("pos_trans_no", "pos_trans_disc_pct",
                "pos_trans_disc_type", "pos_trans_disc_label", "last_receipt"):
        request.session.pop(key, None)

    # messages.success(request, "Session closed successfully.")
    return redirect("pos_logout")




def debug_sessions_json(request):
    sessions = POSSession.objects.prefetch_related(
        'transaction_headers__items', 'transaction_headers__payments'
    ).filter(status="open")

    data = []

    for session in sessions:
        session_data = {
            "id": session.id,
            "cashier": str(session.cashier),
            "terminal_id": session.terminal_id,
            "store_id": session.store_id,
            "business_date": str(session.business_date),
            "status": session.status,
            "transactions": []
        }

        for header in session.transaction_headers.all():
            header_data = {
                "transaction_no": header.transaction_no,
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

    # 🔥 PRINT TO TERMINAL
    # print(json.dumps(data, indent=4))

    # Optional: also return it in browser
    return JsonResponse(data, safe=False)




    # # ── Print ─────────────────────────────────────────────────────────────────
    # ports = {p.port_type: p for p in terminal_config.ports.all()}
    # printer_port = ports.get("PRINTER")
    # # Print all port details
    # print("\n=== ALL PORTS ===")
    # for port_type, port_obj in ports.items():
    #     print(f"\nPort Type: {port_type}")
    #     print(f"  Port Name: {port_obj.port_name}")
    #     print(f"  Connection Type: {port_obj.connection_type}")
    #     print(f"  Baudrate: {port_obj.baudrate}")
    #     print(f"  IP Address: {port_obj.ip_address}")
    #     print(f"  Port No: {port_obj.port_no}")
    #     print(f"  Printer Name: {port_obj.printer_name}")
    
    # # Print printer port details
    # print("\n=== PRINTER PORT ===")
    # if printer_port:
    #     print(f"Port Type: PRINTER")
    #     print(f"  Port Name: {printer_port.port_name}")
    #     print(f"  Connection Type: {printer_port.connection_type}")
    #     print(f"  Baudrate: {printer_port.baudrate}")
    #     print(f"  IP Address: {printer_port.ip_address}")
    #     print(f"  Port No: {printer_port.port_no}")
    #     print(f"  Printer Name: {printer_port.printer_name}")
    # else:
    #     print("❌ No PRINTER port found!")
    
    # print("\n")

    # if not printer_port:
    #     print("❌ Printer port not configured")
    # else:
    #     printer = None
    #     try:
    #         # FIX: connection_type-aware printer open; baudrate read from DB
    #         printer = _open_printer(printer_port)
    #         _print_receipt(printer, terminal_config, context)
    #     except NotImplementedError as e:
    #         print(f"❌ Printer not supported: {e}")
    #     except Exception as e:
    #         print(f"❌ Printer error: {e}")
    #     finally:
    #         if printer is not None:
    #             try:
    #                 printer.close()
    #             except Exception:
    #                 pass



    
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
 
    # ── Header ───────────────────────────────────────────────────────────────
    printer.write(b"\x1b\x61\x01")  # center
    db_headers = list(terminal_config.headers.all().order_by("line_number"))
    for h in db_headers:
        write_line(h.header_text)
    if not db_headers:
        write_line("OTTO Store")
 
    write_line("\nSALES INVOICE\n")
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
 
    void_line_items   = headers_qs.filter(transaction_type="L").aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    void_transactions = headers_qs.filter(transaction_type="V").aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    void_previous     = headers_qs.filter(transaction_type="P").aggregate(total=Sum("items__item_price_ext"), count=Count("id"))
    item_returns      = headers_qs.filter(return_code="R").aggregate(total=Sum("items__item_price_ext"),      count=Count("id"))
    cash_withdrawals  = Payment.objects.filter(header__session=session, pcode="CW").aggregate(total=Sum("amount"), count=Count("id"))
 
    total_neg = sum(filter(None, [
        void_line_items["total"], void_transactions["total"],
        void_previous["total"],   item_returns["total"],
        cash_withdrawals["total"],
    ]))
 
    sales_headers = headers_qs.exclude(transaction_type__in=["V", "L", "P"]).exclude(return_code="R")
 
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
 
    def summary_row(label, amount, count=None):
        amt_str = f"{float(amount or 0):>10,.2f}"
        if count is not None:
            return f"{label:<{paper_width - 16}}{amt_str}{int(count):>5}"
        return f"{label:<{paper_width - 11}}{amt_str}"
 
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
        write_line(f"BEG. SI    : {beg_si}")
        write_line(f"END. SI    : {end_si}")
 
        # ── Negative entries ──────────────────────────────────────────────────
        write_line("Negative Entries")
        write_line(neg_row("Void Line Item",   void_line_items["total"],   void_line_items["count"]))
        write_line(neg_row("Void Transaction", void_transactions["total"], void_transactions["count"]))
        write_line(neg_row("Void Previous",    void_previous["total"],     void_previous["count"]))
        write_line(neg_row("Item Returns",     item_returns["total"],      item_returns["count"]))
        write_line(neg_row("Cash Withdrawal",  cash_withdrawals["total"],  cash_withdrawals["count"]))
        separator()
        write_line(summary_row("Total", total_neg_entries_amt))
 
        # ── Gross sales & discounts ───────────────────────────────────────────
        write_line(summary_row("GROSS SALES", gross_sales))
        write_line("Less:Discounts")
        write_line(neg_row("Item Disc.",     item_disc["total"],       item_disc["count"]))
        write_line(neg_row("Item Amt Disc.", item_amt_disc["total"],   item_amt_disc["count"]))
        write_line(neg_row("Senior % Disc.", senior_disc["total"],     senior_disc["count"]))
        write_line(neg_row("     Amt.Disc.", senior_amt_disc["total"], senior_amt_disc["count"]))
        separator()
        write_line(summary_row("Total", total_disc))
 
        # ── Counts ────────────────────────────────────────────────────────────
        write_line(f"{'Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>16}")
        write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>16}")
        separator()
 
        # ── Tender breakdown ──────────────────────────────────────────────────
        for t in tender_breakdown:
            desc = (t["tender_desc"] or t["pcode"] or "CASH").upper()
            write_line(neg_row(desc, t["total"], t["count"]))
        write_line(neg_row("GC SALES", gc_sales["total"], gc_sales["count"]))
        separator()
        write_line(summary_row("NET SALES", net_sales))
        separator()
 
        # ── Terminal summary ──────────────────────────────────────────────────
        printer.write(b"\x1b\x61\x01")
        write_line(center("Terminal Summary Total"))
        printer.write(b"\x1b\x61\x00")
        separator()
        separator()
        write_line(summary_row("OLD GRAND TOTAL", old_grand_total))
        write_line(summary_row("NEW GRAND TOTAL", new_grand_total))
        separator()
        write_line(f"{'Total Customer Count':<{paper_width - 16}}{fmt_count(customer_count):>16}")
        write_line(f"{'Total Item Sold':<{paper_width - 16}}{fmt_count(total_items_sold):>16}")
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
        separator()
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
        else:
            write_line("Thank you!")
        printer.write(b"\x1b\x61\x00")
 
        # ── Feed & cut ────────────────────────────────────────────────────────
        write_line("\n" * 5)
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
    session = POSSession.objects.select_related("cashier").get(
        id=session.id,
        status="open",
    )
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
        "store_name":       setup_details.header01 or "OTTO Store",
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
        session = POSSession.objects.select_related("cashier").get(
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