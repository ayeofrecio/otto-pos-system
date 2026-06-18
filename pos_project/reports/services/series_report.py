"""
reports/services/series_report.py

Assembles all data needed for the Series (per-session) Sales Report.
Returns a plain dict so the view stays thin and this is independently testable.

Data sources:
  - POSSession              → session scope (store_id, terminal_id, business_date)
  - TerminalConfiguration   → vat rate
  - TerminalReceiptHeader   → BIR / store header lines
  - TransactionHeader       → one row per SI (excludes all void types)
  - TransactionItem         → line items (item_code, description, color, size, qty, amount, tax_code)
  - Payment                 → tender lines per SI (for mode of payment column)
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sales.models import (
    TransactionHeader,
    TransactionItem,
    Payment,
    TerminalConfiguration,
    TerminalReceiptHeader,
)
from users.models import POSSession
from sales.pos_constants import VOID_TRANSACTION_TYPES_ALL


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_vat(amount: Decimal, vat_rate: Decimal, tax_code: str = "V") -> Decimal:
    """
    Compute the VAT component for a single line item.

    V (vatable)   → VAT is embedded in the price (inclusive).
                    vat = amount - (amount / (1 + vat_rate))
    E (exempt)    → 0
    Z (zero-rated)→ 0
    Anything else → 0  (safe default)
    """
    if tax_code == "V" and vat_rate > 0:
        divisor = Decimal("1") + vat_rate
        vat = amount - (amount / divisor)
        return vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0.00")


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
    Returns a context dict ready for the series_report.html template.

    Raises:
        POSSession.DoesNotExist          if session_id is invalid
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
    # Step 3 — Load transaction headers for this session, excluding voids
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
    # Step 5 — Build report rows
    # ------------------------------------------------------------------
    rows = []
    total_qty    = Decimal("0")
    total_amount = Decimal("0")
    total_vat    = Decimal("0")

    vat_rate = terminal.vat  # e.g. Decimal("0.1200")

    for header in transactions:
        payment_mode = _payment_modes(header.payments.all())

        for item in header.items.all():
            vat = _compute_vat(item.item_price_ext, vat_rate or "") #, item.item_tax_code

            rows.append(
                {
                    "si_no":        header.transaction_no,
                    # "date":         header.transaction_date,
                    "item_no":      item.item_code,
                    "item_name":    item.item_description,
                    "color":        item.item_color_desc or item.item_color or "—",
                    "size":         item.item_size or "—",
                    "qty":          item.item_qty,
                    "amount":       item.item_price_ext,
                    "vat":          vat,
                    "payment_mode": payment_mode,
                }
            )

            total_qty    += item.item_qty
            total_amount += item.item_price_ext
            total_vat    += vat

    # ------------------------------------------------------------------
    # Step 6 — Return assembled context
    # ------------------------------------------------------------------
    return {
        # Terminal / store header
        "header_lines":  header_lines,
        "store_id":      session.store_id,
        "terminal_id":   session.terminal_id,
        "business_date": session.business_date,
        "vat_rate":      vat_rate,

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

        # Detail rows
        "rows":          rows,

        # Totals
        "total_qty":     total_qty,
        "total_amount":  total_amount,
        "total_vat":     total_vat,
        "transaction_count": len(transactions),
    }




# """
# reports/services/series_report.py

# Assembles all data needed for the Series (per-session) Sales Report.
# Returns a plain dict so the view stays thin and this is independently testable.

# Data sources:
#   - POSSession              → session scope (store_id, terminal_id, business_date)
#   - TerminalConfiguration   → vat rate
#   - TerminalReceiptHeader   → BIR / store header lines
#   - TransactionHeader       → one row per SI (excludes all void types)
#   - TransactionItem         → line items (item_code, description, color, size, qty, amount, tax_code)
#   - Payment                 → tender lines per SI (for mode of payment column)
# """

# from decimal import Decimal, ROUND_HALF_UP

# from sales.models import (
#     TransactionHeader,
#     TransactionItem,
#     Payment,
#     TerminalConfiguration,
#     TerminalReceiptHeader,
# )
# from users.models import POSSession
# from sales.pos_constants import VOID_TRANSACTION_TYPES_ALL


# # ---------------------------------------------------------------------------
# # Internal helpers
# # ---------------------------------------------------------------------------

# def _compute_vat(amount: Decimal, vat_rate: Decimal, tax_code: str) -> Decimal:
#     """
#     Compute the VAT component for a single line item.

#     V (vatable)   → VAT is embedded in the price (inclusive).
#                     vat = amount - (amount / (1 + vat_rate))
#     E (exempt)    → 0
#     Z (zero-rated)→ 0
#     Anything else → 0  (safe default)
#     """
#     if tax_code == "V" and vat_rate > 0:
#         divisor = Decimal("1") + vat_rate
#         vat = amount - (amount / divisor)
#         return vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
#     return Decimal("0.00")


# def _payment_modes(payments) -> str:
#     """
#     Join all tender descriptions for a header into a readable string.
#     Falls back to pcode if tender_desc is blank.
#     e.g.  "Cash"  /  "Cash, GCash"
#     """
#     labels = []
#     for p in payments:
#         label = (p.tender_desc or p.pcode or "").strip()
#         if label:
#             labels.append(label)
#     return ", ".join(labels) if labels else "—"


# # ---------------------------------------------------------------------------
# # Public entry point
# # ---------------------------------------------------------------------------

# def build_series_report(session_id: int) -> dict:
#     """
#     Returns a context dict ready for the series_report.html template.

#     Raises:
#         POSSession.DoesNotExist          if session_id is invalid
#         TerminalConfiguration.DoesNotExist if terminal config is missing
#     """

#     # ------------------------------------------------------------------
#     # Step 1 — Load session
#     # ------------------------------------------------------------------
#     session = POSSession.objects.select_related("opened_by", "closed_by").get(
#         pk=session_id
#     )

#     # ------------------------------------------------------------------
#     # Step 2 — Load terminal config + receipt header lines
#     # ------------------------------------------------------------------
#     terminal = TerminalConfiguration.objects.get(
#         store_id=session.store_id,
#         terminal_id=session.terminal_id,
#     )

#     header_lines = list(
#         TerminalReceiptHeader.objects.filter(terminal=terminal)
#         .order_by("line_number")
#         .values_list("header_text", flat=True)
#     )

#     # ------------------------------------------------------------------
#     # Step 3 — Load transaction headers for this session, excluding voids
#     # ------------------------------------------------------------------
#     trans_qs = (
#         TransactionHeader.objects.filter(session=session)
#         .exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL)
#         .order_by("transaction_no")
#         .prefetch_related("items", "payments")
#     )

#     transactions = list(trans_qs)

#     # ------------------------------------------------------------------
#     # Step 4 — Beg / End SI
#     # ------------------------------------------------------------------
#     if transactions:
#         beg_si = transactions[0].transaction_no
#         end_si  = transactions[-1].transaction_no
#     else:
#         beg_si = end_si = "—"

#     # ------------------------------------------------------------------
#     # Step 5 — Build report rows
#     # ------------------------------------------------------------------
#     rows = []
#     total_qty    = Decimal("0")
#     total_amount = Decimal("0")
#     total_vat    = Decimal("0")

#     vat_rate = terminal.vat  # e.g. Decimal("0.1200")

#     for header in transactions:
#         payment_mode = _payment_modes(header.payments.all())

#         for item in header.items.all():
#             vat = _compute_vat(item.item_price_ext, vat_rate, item.item_tax_code or "")

#             rows.append(
#                 {
#                     "si_no":        header.transaction_no,
#                     "date":         header.transaction_date,
#                     "item_no":      item.item_code,
#                     "item_name":    item.item_description,
#                     "color":        item.item_color_desc or item.item_color or "—",
#                     "size":         item.item_size or "—",
#                     "qty":          item.item_qty,
#                     "amount":       item.item_price_ext,
#                     "vat":          vat,
#                     "payment_mode": payment_mode,
#                 }
#             )

#             total_qty    += item.item_qty
#             total_amount += item.item_price_ext
#             total_vat    += vat

#     # ------------------------------------------------------------------
#     # Step 6 — Return assembled context
#     # ------------------------------------------------------------------
#     return {
#         # Terminal / store header
#         "header_lines":  header_lines,
#         "store_id":      session.store_id,
#         "terminal_id":   session.terminal_id,
#         "business_date": session.business_date,
#         "vat_rate":      vat_rate,

#         # Session info
#         "session":       session,
#         "opened_by":     session.opened_by.get_full_name() or session.opened_by.username,
#         "closed_by":     (
#             session.closed_by.get_full_name() or session.closed_by.username
#             if session.closed_by else "—"
#         ),
#         "opened_at":     session.opened_at,
#         "closed_at":     session.closed_at,

#         # SI range
#         "beg_si":        beg_si,
#         "end_si":        end_si,

#         # Detail rows
#         "rows":          rows,

#         # Totals
#         "total_qty":     total_qty,
#         "total_amount":  total_amount,
#         "total_vat":     total_vat,
#         "transaction_count": len(transactions),
#     }