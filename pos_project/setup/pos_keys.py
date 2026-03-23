from sales.models import POSFunction      # ← import from sales instead

# Function code constants
P_IVIEW_KEY   = 'pIViewKey'    # Item Viewing
P_IDISC_KEY   = 'pIDiscKey'    # Item Discount
P_STDISC_KEY  = 'pSTDiscKey'   # Sub-total Discount
P_PROVER_KEY  = 'pPrOverKey'   # Price Override
P_IRET_KEY    = 'pIRetKey'     # Item Returns
P_IVOID_KEY   = 'pIVoidKey'    # Item Void
P_IVOIDA_KEY  = 'pIVoidAKey'   # Item Void All
P_VOIDTR_KEY  = 'pVoidTrKey'   # Transaction Void
P_ISUSRT_KEY  = 'pISusRtKey'   # Retrieve Suspended
P_STAT_KEY    = 'pStatKey'     # Net Sales Status
P_SUBTOT_KEY  = 'pSubTotKey'   # SubTotal Key
P_PAYMNT_KEY  = 'pPaymntKey'   # Payment Key
P_IQTY_KEY    = 'pIQtyKey'     # Quantity
P_TSREP_KEY   = 'pTSRepKey'    # X-Reading
P_ZREAD_KEY   = 'pZReadKey'    # Z-Reading
P_JREP_KEY    = 'pJRepKey'     # Journal Report
P_SOFF_KEY    = 'pSOffKey'     # Sign-Off Key
P_MENU_KEY    = 'pMenuKey'     # Help Menu
P_SMAN_KEY    = 'pSManKey'     # Cashier Accountability
P_CWITHD_KEY  = 'pCWithDKey'   # Cash Withdrawal
P_RESEND_TXT  = 'pResendTxt'   # Admin Resend

POS_KEY_CODES = [
    P_IVIEW_KEY, P_IDISC_KEY, P_STDISC_KEY, P_PROVER_KEY,
    P_IRET_KEY,  P_IVOID_KEY, P_IVOIDA_KEY, P_VOIDTR_KEY,
    P_ISUSRT_KEY, P_STAT_KEY, P_SUBTOT_KEY, P_PAYMNT_KEY,
    P_IQTY_KEY,  P_TSREP_KEY, P_ZREAD_KEY,  P_JREP_KEY,
    P_SOFF_KEY,  P_MENU_KEY,  P_SMAN_KEY,   P_CWITHD_KEY,
    P_RESEND_TXT,
]


def get_key_code(code: str) -> str:
    try:
        func = POSFunction.objects.get(code__iexact=code.strip())
        return func.key_code.strip()            # ← key_code not keycode
    except POSFunction.DoesNotExist:
        return ''


def get_pos_keys() -> dict:
    records = POSFunction.objects.filter(
        code__in=[c.strip() for c in POS_KEY_CODES]
    ).values('code', 'key_code')               # ← key_code not keycode

    lookup = {r['code'].strip(): r['key_code'].strip() for r in records}
    return {code: lookup.get(code, '') for code in POS_KEY_CODES}