"""
reports/services/series_report.py

Assembles all data needed for the Series (per-session) Sales Report.
Returns a plain dict so the view stays thin and this is independently testable.

Data sources:
  - POSSession              → session scope (store_id, terminal_id, business_date)
  - TerminalConfiguration   → vat rate
  - TerminalReceiptHeader   → BIR / store header lines
  - TransactionHeader       → one row per SI (excludes all void types)
                              VAT fields read directly from header snapshot
                              (vat_amount, vatable_amount, etc.)
  - TransactionItem         → line items per SI
  - Payment                 → tender lines per SI (mode of payment)
"""

from decimal import Decimal

from sales.models import (
    TransactionHeader,
    TerminalConfiguration,
    TerminalReceiptHeader,
)
from users.models import POSSession
from sales.pos_constants import VOID_TRANSACTION_TYPES_ALL


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _payment_modes(payments) -> str:
    """
    Join all tender descriptions for a header into a readable string.
    Falls back to pcode if tender_desc is blank.
    e.g.  "Cash"  /  "Cash, GCash"
    """
    labels = []
    for p in payments:
        label = (p.tender_desc or p.pcode or "").strip()
        if label:
            labels.append(label)
    return ", ".join(labels) if labels else "—"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_series_report(session_id: int) -> dict:
    """
    Returns a context dict ready for build_series_pdf().

    The key change from the flat-rows design:
      - "invoices" is a list of dicts, one per TransactionHeader.
      - Each invoice has its own total_qty, total_amount, total_vat
        (taken directly from the header snapshot — NOT recomputed per item).
      - Each invoice has an "items" list of line dicts (no VAT per line).

    Raises:
        POSSession.DoesNotExist            if session_id is invalid
        TerminalConfiguration.DoesNotExist if terminal config is missing
    """

    # ------------------------------------------------------------------
    # Step 1 — Load session
    # ------------------------------------------------------------------
    session = POSSession.objects.select_related("opened_by", "closed_by").get(
        pk=session_id
    )

    # ------------------------------------------------------------------
    # Step 2 — Load terminal config + receipt header lines
    # ------------------------------------------------------------------
    terminal = TerminalConfiguration.objects.get(
        store_id=session.store_id,
        terminal_id=session.terminal_id,
    )

    header_lines = list(
        TerminalReceiptHeader.objects.filter(terminal=terminal)
        .order_by("line_number")
        .values_list("header_text", flat=True)
    )

    # ------------------------------------------------------------------
    # Step 3 — Load transaction headers, excluding all void types
    # ------------------------------------------------------------------
    trans_qs = (
        TransactionHeader.objects.filter(session=session)
        .exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL)
        .order_by("transaction_no")
        .prefetch_related("items", "payments")
    )

    transactions = list(trans_qs)

    # ------------------------------------------------------------------
    # Step 4 — Beg / End SI
    # ------------------------------------------------------------------
    if transactions:
        beg_si = transactions[0].transaction_no
        end_si  = transactions[-1].transaction_no
    else:
        beg_si = end_si = "—"

    # ------------------------------------------------------------------
    # Step 5 — Build grouped invoices
    #
    # Structure per invoice:
    #   si_no        — transaction number
    #   payment_mode — comma-joined tender descriptions
    #   total_qty    — sum of item_qty across all items in this SI
    #   total_amount — header.amount_total  (snapshotted)
    #   total_vat    — header.vat_amount    (snapshotted, not recomputed)
    #   items        — list of line dicts (no VAT per line)
    # ------------------------------------------------------------------
    invoices     = []
    grand_qty    = Decimal("0")
    grand_amount = Decimal("0")
    grand_vat    = Decimal("0")

    for header in transactions:
        items = []
        inv_qty = Decimal("0")

        for item in header.items.all():
            items.append({
                "item_no":   item.item_code,
                "item_name": item.item_description,
                "color":     item.item_color_desc or item.item_color or "NO COLOR",
                "size":      item.item_size or "NS",
                "qty":       item.item_qty,
                "amount":    item.item_price_ext,
            })
            inv_qty += item.item_qty

        # VAT from header snapshot — already computed by POS at payment time
        inv_amount = header.amount_total
        inv_vat    = header.vat_amount

        invoices.append({
            "si_no":        header.transaction_no,
            "payment_mode": _payment_modes(header.payments.all()),
            "total_qty":    inv_qty,
            "total_amount": inv_amount,
            "total_vat":    inv_vat,
            "items":        items,
        })

        grand_qty    += inv_qty
        grand_amount += inv_amount
        grand_vat    += inv_vat

    # ------------------------------------------------------------------
    # Step 6 — Return assembled context
    # ------------------------------------------------------------------
    return {
        # Terminal / store header
        "header_lines":  header_lines,
        "store_id":      session.store_id,
        "terminal_id":   session.terminal_id,
        "business_date": session.business_date,
        "vat_rate":      terminal.vat,

        # Session info
        "session":       session,
        "opened_by":     session.opened_by.get_full_name() or session.opened_by.username,
        "closed_by":     (
            session.closed_by.get_full_name() or session.closed_by.username
            if session.closed_by else "—"
        ),
        "opened_at":     session.opened_at,
        "closed_at":     session.closed_at,

        # SI range
        "beg_si":        beg_si,
        "end_si":        end_si,

        # Grouped data
        "invoices":          invoices,
        "transaction_count": len(transactions),

        # Grand totals
        "grand_qty":    grand_qty,
        "grand_amount": grand_amount,
        "grand_vat":    grand_vat,
    }