"""
POS Cashier views: login, cashier screen, cart operations.
"""

import datetime
import django.utils.timezone as timezone
from decimal import Decimal
from pyexpat.errors import messages

from django.db import models
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from users.models import POSSession

from .color_lookup import get_color_description
from .size_lookup import get_size_description
from .decorators import require_open_session
from .models import Item, ItemDetail, TempTransaction, TransactionLog, POSTransCounter, Tender, TerminalSetup, Color, Size
from .services import get_business_date
from .transaction_services.transaction_service import TransactionService, RecordCode

from setup.pos_keys import get_pos_keys


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


def _get_store_name():
    """Return store name from TerminalSetup, or default."""
    try:
        setup = TerminalSetup.objects.get(store_id=STORE_ID, terminal_id=TERMINAL_ID)
        return setup.header01 or "POS Store"
    except TerminalSetup.DoesNotExist:
        return "POS Store"


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


# ---------------------------------------------------------------------------
# Close session view
# ---------------------------------------------------------------------------

@login_required
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
@require_http_methods(["POST"])
def payment_complete(request):
    """
    Complete payment with tender entries. Supports multiple tenders.
    Only completes when total tendered >= amount due.
    
    NOW WITH CLIPPER-STYLE TRANSACTION LOGGING
    """
    user_id = _get_user_id(request)
    trans_no = request.session.get("pos_trans_no")
    tender_entries = _parse_tender_entries(request)

    if not tender_entries:
        return redirect("sales:pay")

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

    total_tendered = sum(amt for _, amt in tender_entries)
    if total_tendered < total:
        # Do not complete - total tendered is less than amount due
        return redirect("sales:pay")

    now = datetime.datetime.now()
    try:
        biz_date = get_business_date(STORE_ID, TERMINAL_ID, now)
    except Exception:
        biz_date = now.date()

    # Build tender entries with full details
    tender_lines = []
    tender_entries_full = []  # For TransactionService
    total_cash = Decimal("0")
    
    for pcode, amt in tender_entries:
        tender = Tender.objects.filter(pcode=pcode).first()
        desc = tender.description if tender else pcode
        is_cash = tender and tender.pchange == "Y"
        
        tender_lines.append({
            "desc": desc,
            "amount": str(amt),
            "is_cash": is_cash
        })
        
        # Prepare for TransactionService
        tender_entries_full.append((pcode, amt, desc, is_cash))
        
        if is_cash:
            total_cash += amt
    
    change_amount = max(Decimal("0"), total_tendered - total) if total_cash > 0 else Decimal("0")
    tender_display = ", ".join(f"{t['desc']} ₱{t['amount']}" for t in tender_lines)

    # ========================================================================
    # CLIPPER-STYLE TRANSACTION LOGGING
    # This replaces the simple loop that was saving cart_lines to TransactionLog
    # ========================================================================
    
    try:
        # Initialize transaction service
        transaction_service = TransactionService()
        
        # Get salesman code (you can get this from session or user profile)
        salesman_code = request.session.get("salesman_code", "")  # Adjust as needed
        
        # Generate SI number (you can customize this format)
        si_number = f"SI-{trans_no}"
        
        # Save to TransactionLog with Clipper business logic
        records_saved = transaction_service.save_to_transaction_log(
            cart_lines=cart_lines_list,
            transaction_no=trans_no,
            transaction_date=biz_date,
            transaction_time=now.strftime("%H:%M"),
            user_id=user_id,
            salesman_code=salesman_code,
            tender_entries=tender_entries_full,
            subtotal_discount_pct=trans_disc.get("pct", Decimal("0")),
            subtotal_discount_label=trans_disc.get("label", ""),
            si_number=si_number,
            void_tag=""  # Empty for normal sales, 'X' for voided transactions
        )
        
        print(f"✓ Saved {records_saved} records to TransactionLog (TLOG)")
        
        # Clear temp table (equivalent to Clipper dropping TEMP.DBF)
        deleted_count = transaction_service.clear_temp_table(user_id, trans_no)
        print(f"✓ Cleared {deleted_count} records from TempTransaction (TEMPTRANS)")
        
    except Exception as e:
        print(f"❌ Transaction logging error: {e}")
        import traceback
        traceback.print_exc()
        # You might want to handle this error differently
        # For now, we'll continue since the old code also saved to TransactionLog
    
    # ========================================================================
    # END TRANSACTION LOGGING
    # ========================================================================

    # Store receipt data for display
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
                "size": get_size_description(line.item_size or ""),
                "color": get_color_description(
                    line.item_color or "",
                    icode=line.item_code or "",
                    size=line.item_size or "",
                ),
            }
            for line in cart_lines_list
        ],
    }

    # Get new transaction number for next transaction
    new_trans = _get_next_transaction_no()
    request.session["pos_trans_no"] = new_trans
    _clear_trans_disc(request)

    return redirect("sales:receipt")





# @login_required
# def receipt_view(request):
#     """Display receipt after payment. Data comes from session."""
#     receipt = request.session.get("last_receipt")
#     if not receipt:
#         return redirect("sales:pos_cashier")

#     tender_lines = receipt.get("tender_lines") or []
#     if not tender_lines and receipt.get("tender"):
#         # Legacy single-tender format
#         tender_lines = [{"desc": receipt["tender"], "amount": receipt.get("amount_tendered", receipt["total"]), "is_cash": receipt.get("is_cash", False)}]

#     context = {
#         "store_name": _get_store_name(),
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
#     return render(request, "sales/receipt.html", context)



@login_required
def receipt_view(request):
    """Display receipt after payment. Data comes from session."""
    receipt = request.session.get("last_receipt")
    if not receipt:
        return redirect("sales:pos_cashier")

    tender_lines = receipt.get("tender_lines") or []
    if not tender_lines and receipt.get("tender"):
        tender_lines = [{
            "desc": receipt["tender"],
            "amount": receipt.get("amount_tendered", receipt["total"]),
            "is_cash": receipt.get("is_cash", False)
        }]

    context = {
        "store_name": _get_store_name(),
        "transaction_no": receipt["transaction_no"],
        "date": receipt["date"],
        "time": receipt["time"],
        "subtotal": receipt.get("subtotal", receipt["total"]),
        "trans_disc_pct": receipt.get("trans_disc_pct", "0"),
        "trans_disc_label": receipt.get("trans_disc_label", ""),
        "trans_disc_amt": receipt.get("trans_disc_amt", "0"),
        "total": receipt["total"],
        "tender": receipt.get("tender", ""),
        "tender_lines": tender_lines,
        "is_cash": receipt.get("is_cash", False),
        "amount_tendered": receipt.get("amount_tendered", ""),
        "change_amount": receipt.get("change_amount", ""),
        "lines": receipt["lines"],
    }

    def format_money(val):
        try:
            return f"{float(val):,.2f}"
        except:
            return str(val)


    # 🔥 PRINT TO EPSON TM-U220
    try:
        printer = serial.Serial(
            port='COM1',   # CHANGE if needed
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )

        time.sleep(1)

        def write_line(text=""):
            printer.write((text + "\n").encode("utf-8"))

        def separator():
            write_line("-" * 32)

        # =============================
        # HEADER
        # =============================
        printer.write(b'\x1b\x61\x01')  # center align
        write_line(context["store_name"])
        printer.write(b'\x1b\x61\x00')  # left align

        write_line(context["date"])
        write_line(context["time"])
        write_line(f"Receipt #{context['transaction_no']}")
        separator()

        # =============================
        # ITEMS
        # =============================
        for line in context["lines"]:
            desc = line.get("description", "")
            ext = format_money(line.get("ext", 0))

            write_line(f"{desc[:28]}")
            write_line(f"{line.get('qty')} x {format_money(line.get('price'))}".ljust(20) + f"{ext}".rjust(12))

            if line.get("disc_pct"):
                write_line(f"  {line.get('disc_pct')}% discount -{format_money(line.get('disc_total'))}")
                write_line(f"  Net: {ext}")

        # =============================
        # TRANSACTION DISCOUNT
        # =============================
        if context["trans_disc_amt"] and context["trans_disc_amt"] not in ["0", "0.0000"]:
            separator()
            write_line(f"Subtotal: {format_money(context['subtotal'])}")
            write_line(f"{context['trans_disc_label']} ({context['trans_disc_pct']}%)")
            write_line(f"-{format_money(context['trans_disc_amt'])}")

        # =============================
        # TOTAL
        # =============================
        separator()
        printer.write(b'\x1b\x45\x01')  # bold on
        write_line(f"TOTAL: {format_money(context['total'])}")
        printer.write(b'\x1b\x45\x00')  # bold off
        separator()

        # =============================
        # TENDER LINES
        # =============================
        for t in context["tender_lines"]:
            write_line(f"{t['desc']}: {format_money(t['amount'])}")

        if context["amount_tendered"]:
            write_line(f"Total Tendered: {format_money(context['amount_tendered'])}")

        if context["is_cash"] and context["change_amount"] not in ["", "0", "0.0000"]:
            printer.write(b'\x1b\x45\x01')
            write_line(f"CHANGE: {format_money(context['change_amount'])}")
            printer.write(b'\x1b\x45\x00')

        # =============================
        # FOOTER
        # =============================
        separator()
        printer.write(b'\x1b\x61\x01')  # center align
        write_line("Thank you for your purchase!")
        write_line("Please come again")
        printer.write(b'\x1b\x61\x00')

        write_line("\n\n\n")

        # Cut paper
        printer.write(b'\x1d\x56\x00')

        printer.close()

    except Exception as e:
        print("❌ Printer Error:", e)
    return render(request, "sales/receipt.html", context)


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
                    "size_display": get_size_description(v.size or ""),
                    "color": v.color,
                    "color_display": get_color_description(v.color, item_detail=v),
                    "price": str(v.price or item.price),
                })
        else:
            results.append({
                "barcode": item.icode,
                "code": item.icode,
                "description": item.short_desc or item.long_desc,
                "size": item.size or "",
                "size_display": get_size_description(item.size or ""),
                "color": item.color or "",
                "color_display": get_color_description(
                    item.color or "",
                    icode=item.icode,
                    size=item.size or "",
                ),
                "price": str(item.price),
            })

    return JsonResponse({"results": results})
