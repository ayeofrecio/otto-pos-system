from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum

from .models import AccountingSummary, TransactionHeader
from .pos_constants import (
    TAG_ITEM_RETURN,
    TRTYPE_VOID_ITEM,
    TRTYPE_VOID_ITEM_LEGACY,
    TRTYPE_VOID_PREVIOUS,
    TRTYPE_VOID_TRANS,
    TRTYPE_VOID_TRANS_LEGACY,
)

D0 = Decimal("0")
D1 = Decimal("1")


def _to_decimal(value, default=D0):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _abs_decimal(value):
    return abs(_to_decimal(value, D0))


def _get_header(header_or_id):
    if isinstance(header_or_id, TransactionHeader):
        return header_or_id
    return TransactionHeader.objects.get(pk=header_or_id)


def _compute_header_delta(header):
    delta = {}

    items_qs = header.items.all()
    item_agg = items_qs.aggregate(total_ext=Sum("item_price_ext"))

    tx_type = (header.transaction_type or "").strip()

    if tx_type in (TRTYPE_VOID_ITEM, TRTYPE_VOID_ITEM_LEGACY):
        delta["void_item_count"] = D1
        delta["void_item_total"] = _abs_decimal(item_agg["total_ext"])
    elif tx_type == TRTYPE_VOID_PREVIOUS:
        delta["void_prev_count"] = D1
        delta["void_prev_total"] = _abs_decimal(item_agg["total_ext"])
    elif tx_type in (TRTYPE_VOID_TRANS, TRTYPE_VOID_TRANS_LEGACY):
        delta["void_trans_count"] = D1
        delta["void_trans_total"] = _abs_decimal(item_agg["total_ext"])
    else:
        sold_qty = items_qs.exclude(tag1=TAG_ITEM_RETURN).aggregate(total_qty=Sum("item_qty"))["total_qty"]
        delta["items_sold"] = _to_decimal(sold_qty)
        # Requested behavior: count each completed transaction as one customer entry.
        delta["customer_count"] = D1

    has_returns = bool((header.return_code or "").strip() == TAG_ITEM_RETURN)
    if not has_returns:
        has_returns = items_qs.filter(tag1=TAG_ITEM_RETURN).exists()

    if has_returns:
        return_total = items_qs.filter(tag1=TAG_ITEM_RETURN).aggregate(total_ext=Sum("item_price_ext"))["total_ext"]
        if return_total in (None, D0):
            return_total = item_agg["total_ext"]
        delta["return_count"] = D1
        delta["return_total"] = _abs_decimal(return_total)

    disc_rows = (
        items_qs.filter(item_discount__gt=0)
        .values("discount_code")
        .annotate(count=Count("id"), total=Sum("item_discount"))
    )
    for row in disc_rows:
        code = (row.get("discount_code") or "").upper()
        count = _to_decimal(row.get("count"))
        total = _abs_decimal(row.get("total"))
        if code == "ID":
            delta["item_disc_count"] = delta.get("item_disc_count", D0) + count
            delta["item_disc_total"] = delta.get("item_disc_total", D0) + total
        elif code == "IA":
            delta["item_disc_a_count"] = delta.get("item_disc_a_count", D0) + count
            delta["item_disc_a_total"] = delta.get("item_disc_a_total", D0) + total
        else:
            delta["item_disc_count"] = delta.get("item_disc_count", D0) + count
            delta["item_disc_total"] = delta.get("item_disc_total", D0) + total

    trans_disc_amt = _abs_decimal(header.trans_disc_amount)
    if trans_disc_amt > D0:
        delta["trans_disc_count"] = D1
        delta["trans_disc_total"] = trans_disc_amt
        if (header.trans_disc_type or "").lower() == "amt":
            delta["trans_disc_a_count"] = D1
            delta["trans_disc_a_total"] = trans_disc_amt

    payment_rows = header.payments.values("pcode").annotate(count=Count("id"), total=Sum("amount"))
    for row in payment_rows:
        pcode = (row.get("pcode") or "").upper()
        count = _to_decimal(row.get("count"))
        total = _abs_decimal(row.get("total"))

        if pcode.startswith("P") and len(pcode) == 3 and pcode[1:].isdigit():
            suffix = pcode.lower()
            count_field = f"{suffix}_count"
            total_field = f"{suffix}_total"
            delta[count_field] = delta.get(count_field, D0) + count
            delta[total_field] = delta.get(total_field, D0) + total
        elif pcode == "CW":
            delta["withdrawal_count"] = delta.get("withdrawal_count", D0) + count
            delta["withdrawal_total"] = delta.get("withdrawal_total", D0) + total

    return delta


@transaction.atomic
def save_accounting_summary(header_or_id):
    """
    Apply per-transaction delta into ACCT (AccountingSummary).
    Key: (store_id, terminal_id, transaction_date, user_id).
    """
    header = _get_header(header_or_id)
    key = {
        "store_id": header.store_id,
        "terminal_id": header.terminal_id,
        "transaction_date": header.transaction_date,
        "user_id": header.user_id,
    }

    acct = AccountingSummary.objects.select_for_update().filter(**key).first()
    if acct is None:
        try:
            acct = AccountingSummary.objects.create(**key)
        except IntegrityError:
            acct = AccountingSummary.objects.select_for_update().get(**key)

    delta = _compute_header_delta(header)

    changed_fields = []
    for field, value in delta.items():
        if value in (None, D0):
            continue
        current = _to_decimal(getattr(acct, field, D0), D0)
        setattr(acct, field, current + value)
        changed_fields.append(field)

    trans_no = (header.transaction_no or "").strip()
    if trans_no:
        if not acct.first_trans_no or trans_no < acct.first_trans_no:
            acct.first_trans_no = trans_no
            changed_fields.append("first_trans_no")
        if not acct.last_trans_no or trans_no > acct.last_trans_no:
            acct.last_trans_no = trans_no
            changed_fields.append("last_trans_no")

    if changed_fields:
        acct.save(update_fields=sorted(set(changed_fields)))

    return acct
