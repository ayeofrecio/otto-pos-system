"""
z_reading_db.py
───────────────
Handles the database-side of a Z-Reading:
  • _aggregate_z_reading_data(session)  – shared data-gathering function
  • update_z_reading_db(session, user)  – writes POSTransNumber + AccountingSummary

Call update_z_reading_db() right after _do_print_z_reading() succeeds.
"""

from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum

from sales.models import (
    AccountingSummary,
    POSTransNumber,
    Payment,
    Tender,
    TransactionHeader,
    TransactionItem,
)
from sales.pos_constants import (
    TRTYPE_VOID_ITEM,
    TRTYPE_VOID_ITEM_LEGACY,
    TRTYPE_VOID_PREVIOUS,
    TRTYPE_VOID_TRANS,
    TRTYPE_VOID_TRANS_LEGACY,
    VOID_TRANSACTION_TYPES_ALL,
)

VAT_RATE = Decimal("0.12")

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Shared aggregation helper
# ---------------------------------------------------------------------------

def _aggregate_z_reading_data(session) -> dict:
    """
    Re-runs the same aggregations used in _do_print_z_reading so that DB
    writes are guaranteed to match what was printed.

    Returns a plain dict with every value needed by update_z_reading_db().
    """
    headers_qs   = TransactionHeader.objects.filter(session=session)
    sales_headers = (
        headers_qs
        .exclude(transaction_type__in=VOID_TRANSACTION_TYPES_ALL)
        .exclude(return_code="R")
    )

    # ── SI range ────────────────────────────────────────────────────────────
    si_numbers = headers_qs.order_by("transaction_no").values_list("transaction_no", flat=True)
    beg_si = si_numbers.first() or "00000000"
    end_si = si_numbers.last()  or "00000000"

    # ── Negative entries ────────────────────────────────────────────────────
    void_line_items   = headers_qs.filter(
        transaction_type__in=[TRTYPE_VOID_ITEM, TRTYPE_VOID_ITEM_LEGACY]
    ).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))

    void_transactions = headers_qs.filter(
        transaction_type__in=[TRTYPE_VOID_TRANS, TRTYPE_VOID_TRANS_LEGACY]
    ).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))

    void_previous = headers_qs.filter(
        transaction_type=TRTYPE_VOID_PREVIOUS
    ).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))

    item_returns = headers_qs.filter(
        return_code="R"
    ).aggregate(total=Sum("items__item_price_ext"), count=Count("id"))

    item_returns_orig_price = headers_qs.filter(
        return_code="R"
    ).aggregate(total=Sum("items__item_price"), count=Count("id"))

    cash_withdrawals = Payment.objects.filter(
        header__session=session, pcode="CW"
    ).aggregate(total=Sum("amount"), count=Count("id"))

    # ── Discounts ────────────────────────────────────────────────────────────
    def _disc(code):
        return TransactionItem.objects.filter(
            header__in=sales_headers, discount_code=code
        ).aggregate(total=Sum("item_discount"), count=Count("id"))

    item_disc       = _disc("EMP")
    pwd_disc        = _disc("PWD")
    item_amt_disc   = _disc("IA")
    senior_disc     = _disc("SC")
    senior_amt_disc = _disc("SA")

    total_disc = sum(
        x["total"] or Decimal("0")
        for x in [item_disc, pwd_disc, item_amt_disc, senior_disc, senior_amt_disc]
    )
    item_disc_count   = (item_disc["count"]   or 0) + (pwd_disc["count"] or 0)
    item_disc_total   = (item_disc["total"]   or Decimal("0")) + (pwd_disc["total"] or Decimal("0"))
    item_disc_a_count = item_amt_disc["count"]   or 0
    item_disc_a_total = item_amt_disc["total"]   or Decimal("0")

    # Transaction-level discounts (senior % and amount)
    trans_disc_count   = senior_disc["count"]     or 0
    trans_disc_total   = senior_disc["total"]     or Decimal("0")
    trans_disc_a_count = senior_amt_disc["count"] or 0
    trans_disc_a_total = senior_amt_disc["total"] or Decimal("0")

    # ── Gross / net sales ────────────────────────────────────────────────────
    gross_sales = (
        TransactionItem.objects
        .filter(header__in=headers_qs)
        .aggregate(total=Sum("item_price_ext"))["total"] or Decimal("0")
    )
    item_returns_orig_price_total = item_returns_orig_price["total"] or Decimal("0")
    final_gross_sales = gross_sales - item_returns_orig_price_total
    net_sales = final_gross_sales - Decimal(str(total_disc))

    # ── VAT ──────────────────────────────────────────────────────────────────
    vatable_sales = net_sales / (1 + VAT_RATE)
    vat_amount    = net_sales - vatable_sales

    # ── Counts ───────────────────────────────────────────────────────────────
    customer_count   = sales_headers.aggregate(total=Sum("customer_count"))["total"] or 0
    total_items_sold = (
        TransactionItem.objects.filter(header__in=sales_headers)
        .aggregate(total=Sum("item_qty"))["total"] or 0
    )

    # ── Tender breakdown mapped to P01–P24 buckets ───────────────────────────
    tender_configs = list(Tender.objects.order_by("pcode"))  # pcode = "p01".."p24"
    tender_payments = (
        Payment.objects
        .filter(header__in=sales_headers)
        .values("pcode")
        .annotate(total=Sum("amount"), count=Count("id"))
    )
    pcode_map = {row["pcode"]: row for row in tender_payments}

    p_buckets = {}   # {"p01_count": n, "p01_total": d, ...}
    for i, tender in enumerate(tender_configs, start=1):
        key = f"p{i:02d}"
        row = pcode_map.get(tender.pcode, {})
        p_buckets[f"{key}_count"] = Decimal(str(row.get("count") or 0))
        p_buckets[f"{key}_total"] = row.get("total") or Decimal("0")

    # ── Void totals for AccountingSummary ────────────────────────────────────
    void_item_count  = void_line_items["count"]   or 0
    void_item_total  = abs(void_line_items["total"]   or Decimal("0"))
    void_trans_count = void_transactions["count"] or 0
    void_trans_total = abs(void_transactions["total"] or Decimal("0"))
    void_prev_count  = void_previous["count"]     or 0
    void_prev_total  = abs(void_previous["total"] or Decimal("0"))
    return_count     = item_returns["count"]      or 0
    return_total     = abs(item_returns["total"]  or Decimal("0"))
    withdrawal_count = cash_withdrawals["count"]  or 0
    withdrawal_total = cash_withdrawals["total"]  or Decimal("0")

    return {
        # SI range
        "beg_si": beg_si,
        "end_si": end_si,
        # Sales
        "gross_sales": gross_sales,
        "net_sales": net_sales,
        "total_disc": total_disc,
        # VAT
        "vatable_sales": vatable_sales,
        "vat_amount": vat_amount,
        # Counts
        "customer_count": customer_count,
        "total_items_sold": total_items_sold,
        # Discounts (for AccountingSummary fields)
        "item_disc_count": item_disc_count,
        "item_disc_total": item_disc_total,
        "item_disc_a_count": item_disc_a_count,
        "item_disc_a_total": item_disc_a_total,
        "trans_disc_count": trans_disc_count,
        "trans_disc_total": trans_disc_total,
        "trans_disc_a_count": trans_disc_a_count,
        "trans_disc_a_total": trans_disc_a_total,
        # Voids / returns / withdrawals
        "void_item_count": void_item_count,
        "void_item_total": void_item_total,
        "void_trans_count": void_trans_count,
        "void_trans_total": void_trans_total,
        "void_prev_count": void_prev_count,
        "void_prev_total": void_prev_total,
        "return_count": return_count,
        "return_total": return_total,
        "withdrawal_count": withdrawal_count,
        "withdrawal_total": withdrawal_total,
        # P01–P24 tender buckets
        **p_buckets,
    }


# ---------------------------------------------------------------------------
# Main DB-update entry point
# ---------------------------------------------------------------------------

@transaction.atomic
def update_z_reading_db(session, user) -> dict:
    """
    Call this immediately after _do_print_z_reading() succeeds.

    Updates:
      • POSTransNumber  – grand totals, prev/curr counters, transaction_no
      • AccountingSummary – full session summary (upsert)

    Returns the aggregated data dict so the caller can log or inspect it.

    Raises ValueError if POSTransNumber doesn't exist (seeding issue).
    """
    data = _aggregate_z_reading_data(session)

    # ── 1. POSTransNumber ────────────────────────────────────────────────────
    try:
        pos_nbr = POSTransNumber.objects.select_for_update().get()
    except POSTransNumber.DoesNotExist:
        raise ValueError(
            "POSTransNumber row not found. Run the seed migration first."
        )

    old_grand_tot = pos_nbr.grand_tot

    pos_nbr.transaction_no = data["end_si"]
    pos_nbr.grand_tot      = old_grand_tot + data["gross_sales"]   # cumulative
    pos_nbr.grand_tot2     = data["net_sales"]                     # this session's net
    pos_nbr.prev_ctr       = pos_nbr.curr_ctr                      # roll over
    pos_nbr.curr_ctr       = Decimal("0")                          # reset for next session
    pos_nbr.save()

    # ── 2. AccountingSummary (upsert) ────────────────────────────────────────
    acct_fields = {
        # Sales / counts
        "items_sold":        Decimal(str(data["total_items_sold"])),
        "customer_count":    Decimal(str(data["customer_count"])),
        # Returns
        "return_count":      Decimal(str(data["return_count"])),
        "return_total":      data["return_total"],
        # Void – item level
        "void_item_count":   Decimal(str(data["void_item_count"])),
        "void_item_total":   data["void_item_total"],
        # Void – previous transaction
        "void_prev_count":   Decimal(str(data["void_prev_count"])),
        "void_prev_total":   data["void_prev_total"],
        # Void – full transaction
        "void_trans_count":  Decimal(str(data["void_trans_count"])),
        "void_trans_total":  data["void_trans_total"],
        # Item discounts
        "item_disc_count":   Decimal(str(data["item_disc_count"])),
        "item_disc_total":   data["item_disc_total"],
        "item_disc_a_count": Decimal(str(data["item_disc_a_count"])),
        "item_disc_a_total": data["item_disc_a_total"],
        # Transaction discounts
        "trans_disc_count":   Decimal(str(data["trans_disc_count"])),
        "trans_disc_total":   data["trans_disc_total"],
        "trans_disc_a_count": Decimal(str(data["trans_disc_a_count"])),
        "trans_disc_a_total": data["trans_disc_a_total"],
        # Withdrawals
        "withdrawal_count":  Decimal(str(data["withdrawal_count"])),
        "withdrawal_total":  data["withdrawal_total"],
        # SI range
        "first_trans_no":    data["beg_si"],
        "last_trans_no":     data["end_si"],
        # Readings
        "x_reading":   data["net_sales"],
        "z_reading":   data["net_sales"],
        "old_total":   old_grand_tot,
        "new_total":   pos_nbr.grand_tot,   # already updated above
        # VAT
        "non_vat":  Decimal("0"),
        "vatable":  data["vatable_sales"],
    }

    # Merge in P01–P24 tender bucket fields
    for i in range(1, 25):
        key = f"p{i:02d}"
        acct_fields[f"{key}_count"] = data.get(f"{key}_count", Decimal("0"))
        acct_fields[f"{key}_total"] = data.get(f"{key}_total", Decimal("0"))

    AccountingSummary.objects.update_or_create(
        store_id=session.store_id,
        terminal_id=session.terminal_id,
        transaction_date=session.business_date,
        user_id=str(user.id),
        defaults=acct_fields,
    )

    return data


