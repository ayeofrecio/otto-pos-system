import datetime
from decimal import Decimal

from django.db import models


class TransactionHeader(models.Model):
    """
    One row per transaction. Replaces the repeated header fields
    that lived on every line in the old flat TLOG/TEMPTRANS structure.
    """
    session = models.ForeignKey(
        'users.POSSession',
        on_delete=models.CASCADE,
        related_name='transaction_headers'
    )

    # Clarion identity fields — kept here for migration traceability
    user_id            = models.CharField(max_length=10)               # USERID
    user_id2           = models.CharField(max_length=4,  blank=True)   # USERID2
    terminal_id        = models.CharField(max_length=3)                # TERMID
    store_id           = models.CharField(max_length=3)                # STOREID

    transaction_no     = models.CharField(max_length=8, db_index=True) # TRNBR
    transaction_date   = models.DateField()                            # TRDATE
    transaction_date_r = models.DateField(null=True, blank=True)       # TRDATER
    transaction_time   = models.CharField(max_length=5,  blank=True)   # TRTIME
    transaction_type   = models.CharField(max_length=1,  blank=True)   # TRTYPE

    # Transaction-level discount
    trans_disc_type   = models.CharField(max_length=10, blank=True, default="")  # "pct" or "amt"
    trans_disc_pct    = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # e.g. 20.00
    trans_disc_label  = models.CharField(max_length=30, blank=True, default="")  # e.g. "Senior"
    trans_disc_amount = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # computed

    # Totals snapshot
    subtotal          = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    amount_total      = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    amount_tendered   = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    change_amount     = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    # VAT breakdown snapshot — computed at payment time
    vat_rate          = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.12"))
    vatable_amount    = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # net of VAT
    vat_amount        = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # VAT portion
    vat_exempt_amount = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    zero_rated_amount = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    return_code        = models.CharField(max_length=1,  blank=True)   # RCODE
    item_ref           = models.CharField(max_length=8,  blank=True)   # TRREF1

    table_id           = models.CharField(max_length=3,  blank=True)   # TABLEID
    served_by          = models.CharField(max_length=20, blank=True)   # SERVEBY
    customer_count     = models.CharField(max_length=10, blank=True)   # CUSTCNT

    class Meta:
        db_table = 'transaction_header'
        indexes = [
            models.Index(fields=['transaction_no', 'transaction_date']),
            models.Index(fields=['store_id', 'terminal_id', 'transaction_date']),
        ]

    def __str__(self):
        return f'{self.transaction_no} / {self.transaction_date}'



class TransactionItem(models.Model):
    """
    One row per line item. FK to TransactionHeader instead of
    repeating header fields on every row.
    """
    header = models.ForeignKey(
        TransactionHeader,
        on_delete=models.CASCADE,
        related_name='items'
    )

    item_code          = models.CharField(max_length=15, blank=True)   # ITEMCODE
    item_description   = models.CharField(max_length=25, blank=True)   # IDESC
    item_qty           = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    item_uom           = models.CharField(max_length=6,  blank=True)
    item_supplier      = models.CharField(max_length=6,  blank=True)
    item_department    = models.CharField(max_length=4,  blank=True)
    item_class         = models.CharField(max_length=4,  blank=True)
    item_size          = models.CharField(max_length=3,  blank=True)
    item_color         = models.CharField(max_length=3,  blank=True)
    item_type          = models.CharField(max_length=1,  blank=True)

    item_cost          = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    item_price         = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    item_discount      = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    discount_code      = models.CharField(max_length=3,  blank=True)
    item_price_ext     = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    tag1               = models.CharField(max_length=1,  blank=True)
    tag2               = models.CharField(max_length=1,  blank=True)
    tag3               = models.CharField(max_length=1,  blank=True)
    tag4               = models.CharField(max_length=1,  blank=True)
    promo_tag          = models.CharField(max_length=1,  blank=True)

    class Meta:
        db_table = 'transaction_item'
        indexes = [
            models.Index(fields=['item_code']),
        ]

    def __str__(self):
        return f'{self.header.transaction_no} / {self.item_code}'


class AccountingSummary(models.Model):
    """
    Equivalent of the Clarion ACCT table.
    One row per cashier session per business day per terminal.
    Holds all X-reading / Z-reading summary totals, void/return counters,
    discount counters, and 24 configurable payment-type buckets (P01–P24).
    Used as the Phase 0 migration target for import_clarion.py.
    """

    # --- Session identifiers ---
    store_id         = models.CharField(max_length=3)                  # STOREID
    terminal_id      = models.CharField(max_length=3)                  # TERMID
    transaction_date = models.DateField()                              # TRDATE
    user_id          = models.CharField(max_length=10)                 # USERID

    # --- Sales totals ---
    items_sold       = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ISOLD
    customer_count   = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # CUSTCNT (REAL in Clarion)

    # --- Returns ---
    return_count     = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # IRETCNT
    return_total     = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IRETTOT

    # --- Void (item level) ---
    void_item_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # IVOIDCNT
    void_item_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IVOIDTOT

    # --- Void (previous transaction) ---
    void_prev_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # TRVPRVCNT
    void_prev_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # TRVPRVTOT

    # --- Void (transaction level) ---
    void_trans_count = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # TRVOIDCNT
    void_trans_total = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # TRVOIDTOT

    # --- Item discounts ---
    item_disc_count   = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # IDISCCNT
    item_disc_total   = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IDISCTOT
    item_disc_a_count = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # IDISCACNT
    item_disc_a_total = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IDISCATOT

    # --- Transaction discounts ---
    trans_disc_count   = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # TDISCCNT
    trans_disc_total   = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # TDISCTOT
    trans_disc_a_count = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # TDISCACNT
    trans_disc_a_total = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # TDISCATOT

    # --- Cash withdrawals / payouts ---
    withdrawal_count = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # WITHDCNT
    withdrawal_total = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # WITHDTOT

    # --- Transaction range ---
    first_trans_no   = models.CharField(max_length=8, blank=True)      # FTRNBR
    last_trans_no    = models.CharField(max_length=8, blank=True)       # LTRNBR

    # --- Readings ---
    x_reading        = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # XREADING
    z_reading        = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ZREADING
    old_total        = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # OLDTOTAL (cumulative before this session)
    new_total        = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # NEWTOTAL (cumulative after this session)

    # --- Payment type buckets P01–P24 (count + total each) ---
    # Each pair maps to a configurable tender type (cash, card, GCash, etc.)
    p01_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P01CNT
    p01_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P01TTL
    p02_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P02CNT
    p02_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P02TTL
    p03_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P03CNT
    p03_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P03TTL
    p04_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P04CNT
    p04_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P04TTL
    p05_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P05CNT
    p05_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P05TTL
    p06_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P06CNT
    p06_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P06TTL
    p07_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P07CNT
    p07_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P07TTL
    p08_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P08CNT
    p08_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P08TTL
    p09_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P09CNT
    p09_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P09TTL
    p10_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P10CNT
    p10_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P10TTL
    p11_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P11CNT
    p11_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P11TTL
    p12_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P12CNT
    p12_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P12TTL
    p13_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P13CNT
    p13_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P13TTL
    p14_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P14CNT
    p14_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P14TTL
    p15_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P15CNT
    p15_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P15TTL
    p16_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P16CNT
    p16_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P16TTL
    p17_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P17CNT
    p17_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P17TTL
    p18_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P18CNT
    p18_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P18TTL
    p19_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P19CNT
    p19_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P19TTL
    p20_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P20CNT
    p20_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P20TTL
    p21_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P21CNT
    p21_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P21TTL
    p22_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P22CNT
    p22_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P22TTL
    p23_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P23CNT
    p23_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P23TTL
    p24_count  = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # P24CNT
    p24_total  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # P24TTL

    # --- VAT breakdown ---
    non_vat  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # NONVAT
    vatable  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # VATABLE

    class Meta:
        db_table = 'acct'
        unique_together = [['store_id', 'terminal_id', 'transaction_date', 'user_id']]
        indexes = [
            models.Index(fields=['store_id', 'terminal_id', 'transaction_date']),
        ]

    def __str__(self):
        return f'{self.store_id}/{self.terminal_id} – {self.transaction_date} – {self.user_id}'


# ---------------------------------------------------------------------------
# SETUP  →  Terminal / store configuration
# (will move to settings_app once that app is built)
# ---------------------------------------------------------------------------
# TO BE REMOVED: This is currently used as the Phase 0 migration target for import_clarion.py, but will be replaced by TerminalConfiguration once the Setup app is built. The fields will be split into related tables for receipt headers/footers and ports, but the TerminalConfiguration model will still have a one-to-one relationship with TerminalSetup for the tax and business hours fields.
class TerminalSetup(models.Model):
    """
    Equivalent of the Clarion SETUP table.
    One row per store/terminal combination. Stores receipt header/footer
    lines, printer/drawer/display port names, and the VAT rate.
    Primary key: (store_id, terminal_id).
    """

    store_id       = models.CharField(max_length=3)                   # STOREID
    terminal_id    = models.CharField(max_length=3)                   # TERMID

    # --- Receipt header lines ---
    header01       = models.CharField(max_length=40, blank=True)      # HEADER01
    header02       = models.CharField(max_length=40, blank=True)      # HEADER02
    header03       = models.CharField(max_length=40, blank=True)      # HEADER03
    header04       = models.CharField(max_length=40, blank=True)      # HEADER04
    header05       = models.CharField(max_length=40, blank=True)      # HEADER05
    header06       = models.CharField(max_length=40, blank=True)      # HEADER06

    # --- Receipt footer lines ---
    footer01       = models.CharField(max_length=40, blank=True)      # FOOTER01
    footer02       = models.CharField(max_length=40, blank=True)      # FOOTER02
    footer03       = models.CharField(max_length=40, blank=True)      # FOOTER03
    footer04       = models.CharField(max_length=40, blank=True)      # FOOTER04

    # --- Hardware ports ---
    draw_port      = models.CharField(max_length=4, blank=True)       # DRAWPORT  (cash drawer)
    print_port     = models.CharField(max_length=4, blank=True)       # PRINTPORT (receipt printer)
    disp_port      = models.CharField(max_length=4, blank=True)       # DISPPORT  (pole display)

    # --- Pole display codes ---
    pdsp_code_f1   = models.CharField(max_length=5, blank=True)       # PDSPCODEF1
    pdsp_code_l1   = models.CharField(max_length=2, blank=True)       # PDSPCODEL1
    pdsp_code_f2   = models.CharField(max_length=5, blank=True)       # PDSPCODEF2
    pdsp_code_l2   = models.CharField(max_length=2, blank=True)       # PDSPCODEL2

    # --- Tax ---
    vat            = models.DecimalField(max_digits=8, decimal_places=4, default=0)  # VAT

    # --- Business hours ---
    open_time   = models.TimeField(default=datetime.time(9, 0))    # 09:00 – cashier login allowed
    cutoff_time = models.TimeField(default=datetime.time(4, 0))    # 04:00 – late-night sales cut off

    class Meta:
        db_table = 'setup'
        unique_together = [['store_id', 'terminal_id']]

    def __str__(self):
        return f'{self.store_id}/{self.terminal_id}'


# ---------------------------------------------------------------------------
# TEMPTRANS  →  Active in-progress cart (current transaction being rung)
# ---------------------------------------------------------------------------

class TempTransaction(models.Model):
    """
    Equivalent of the Clarion TEMPTRANS table.
    Holds the active cart lines while a cashier is ringing a sale.
    Cleared when the transaction is finalised or voided.
    Primary key: rec_ctr (auto-assigned row counter).
    """

    # --- Session identifiers ---
    user_id            = models.CharField(max_length=10)               # USERID
    terminal_id        = models.CharField(max_length=3)                # TERMID
    store_id           = models.CharField(max_length=3)                # STOREID

    # --- Transaction header ---
    transaction_no     = models.CharField(max_length=8)                # TRNBR
    transaction_date   = models.DateField(null=True, blank=True)       # TRDATE
    transaction_date_r = models.DateField(null=True, blank=True)       # TRDATER
    transaction_time   = models.CharField(max_length=5, blank=True)    # TRTIME
    transaction_type   = models.CharField(max_length=1, blank=True)    # TRTYPE
    return_code        = models.CharField(max_length=1, blank=True)    # RCODE
    item_ref           = models.CharField(max_length=8, blank=True)    # TRREF1

    # --- Item detail ---
    item_code          = models.CharField(max_length=15, blank=True)   # ITEMCODE
    item_description   = models.CharField(max_length=25, blank=True)   # IDESC
    item_qty           = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IQTY
    item_uom           = models.CharField(max_length=6, blank=True)    # IUOM
    item_supplier      = models.CharField(max_length=6, blank=True)    # ISUPP
    item_department    = models.CharField(max_length=4, blank=True)    # IDEPT
    item_class         = models.CharField(max_length=4, blank=True)    # ICLASS
    item_size          = models.CharField(max_length=3, blank=True)    # ISIZE
    item_color         = models.CharField(max_length=3, blank=True)    # ICOLOR
    item_type          = models.CharField(max_length=1, blank=True)    # ITYPE
    item_tax_code      = models.CharField(max_length=1, blank=True)    # ITAXC
    table_id           = models.CharField(max_length=3, blank=True)    # TABLEID

    # --- Pricing ---
    item_cost          = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ICOST
    item_price         = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IPRICE
    item_discount      = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IDISC
    discount_code      = models.CharField(max_length=3, blank=True)    # IDISCCODE
    item_price_ext     = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IPRICEE
    old_price          = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # OLDPRICE
    price_override     = models.CharField(max_length=3, blank=True)    # PRICEOVER

    # --- Tags / flags ---
    tag1               = models.CharField(max_length=1, blank=True)    # ITAG1
    tag2               = models.CharField(max_length=1, blank=True)    # ITAG2
    tag3               = models.CharField(max_length=1, blank=True)    # ITAG3
    tag4               = models.CharField(max_length=1, blank=True)    # ITAG4
    promo_tag          = models.CharField(max_length=1, blank=True)    # PTAG
    tag                = models.CharField(max_length=1, blank=True)    # TAG

    # --- Row tracking ---
    transaction_no_ctr  = models.CharField(max_length=8, blank=True)   # TRNBRCTR
    transaction_no_ctr2 = models.CharField(max_length=8, blank=True)   # TRNBRCTR_
    rec_ctr             = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # RECCTR (primary key in Clarion)
    rec_num             = models.CharField(max_length=256, blank=True)  # RECNUM

    # --- Computed helpers (no DB column) ---

    @property
    def item_gross(self):
        """Unit price × qty — the pre-discount extended amount."""
        return (self.item_price or Decimal('0')) * (self.item_qty or Decimal('0'))

    @property
    def item_disc_total(self):
        """Total peso discount for this line (per-unit discount × qty)."""
        return (self.item_discount or Decimal('0')) * (self.item_qty or Decimal('0'))

    @property
    def disc_pct(self):
        """Discount as a percentage (e.g. 10.0 for 10%). Returns 0 when no discount."""
        if self.item_price and self.item_discount:
            return round(float(self.item_discount / self.item_price * 100), 4)
        return 0

    class Meta:
        db_table = 'temptrans'
        indexes = [
            models.Index(fields=['rec_ctr']),
            models.Index(fields=['item_code']),
        ]

    def __str__(self):
        return f'{self.transaction_no} / {self.item_code}'




# ---------------------------------------------------------------------------
# TENDERS  →  Payment tender type configuration
# ---------------------------------------------------------------------------

class Tender(models.Model):
    """
    Equivalent of the Clarion TENDERS table.
    One row per configured payment method (cash, card, GCash, etc.).
    Maps to the P01–P24 buckets in AccountingSummary.
    Primary key: pcode.
    """

    pcode       = models.CharField(max_length=3, unique=True)          # PCODE  (e.g. "P01")
    key_name    = models.CharField(max_length=6, blank=True)           # KEYNAME
    description = models.CharField(max_length=15, blank=True)          # PDESC

    # --- Behaviour flags (single-char Y/N flags in Clarion) ---
    pallow      = models.CharField(max_length=1, blank=True)           # PALLOW   (allowed)
    pfrank      = models.CharField(max_length=1, blank=True)           # PFRANK   (franchise)
    pbal        = models.CharField(max_length=1, blank=True)           # PBAL     (balance)
    pacct       = models.CharField(max_length=1, blank=True)           # PACCT    (account)
    pdocment    = models.CharField(max_length=1, blank=True)           # PDOCMENT (requires document/ref no)
    pchange     = models.CharField(max_length=1, blank=True)           # PCHANGE  (gives change)
    pmarkup     = models.CharField(max_length=1, blank=True)           # PMARKUP  (has markup)
    pmarkamt    = models.DecimalField(max_digits=12, decimal_places=4, default=0)  # PMARKAMT
    pexpiry     = models.CharField(max_length=1, blank=True)           # PEXPIRY  (has expiry)
    pcharge     = models.CharField(max_length=1, blank=True)           # PCHARGE  (has surcharge)
    pconvert    = models.CharField(max_length=1, blank=True)           # PCONVERT (currency convert)

    # --- Keyboard shortcut characters ---
    keychar1    = models.CharField(max_length=1, blank=True)           # KEYCHAR1
    keychar2    = models.CharField(max_length=1, blank=True)           # KEYCHAR2
    keychar3    = models.CharField(max_length=1, blank=True)           # KEYCHAR3
    keychar4    = models.CharField(max_length=1, blank=True)           # KEYCHAR4

    class Meta:
        db_table = 'tenders'

    def __str__(self):
        return f'{self.pcode} – {self.description}'


# ---------------------------------------------------------------------------
# SUSPEND  →  Held / parked transactions
# ---------------------------------------------------------------------------

class SuspendedTransaction(models.Model):
    """
    Equivalent of the Clarion SUSPEND table.
    Stores cart lines for transactions that have been put on hold
    (parked) so the cashier can start another sale.
    Keys: table_id (DUP), (trnbr, rec_ctr) (DUP), item_code (DUP).
    """

    # --- Session identifiers ---
    user_id            = models.CharField(max_length=10)               # USERID
    user_id2           = models.CharField(max_length=4, blank=True)    # USERID2
    terminal_id        = models.CharField(max_length=3)                # TERMID
    store_id           = models.CharField(max_length=3)                # STOREID

    # --- Transaction header ---
    transaction_no     = models.CharField(max_length=8)                # TRNBR
    transaction_date   = models.DateField(null=True, blank=True)       # TRDATE
    transaction_date_r = models.DateField(null=True, blank=True)       # TRDATER
    transaction_time   = models.CharField(max_length=5, blank=True)    # TRTIME
    transaction_type   = models.CharField(max_length=1, blank=True)    # TRTYPE
    return_code        = models.CharField(max_length=1, blank=True)    # RCODE
    item_ref           = models.CharField(max_length=8, blank=True)    # TRREF1

    # --- Item detail ---
    item_code          = models.CharField(max_length=15, blank=True)   # ITEMCODE
    item_description   = models.CharField(max_length=25, blank=True)   # IDESC
    item_qty           = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IQTY
    item_uom           = models.CharField(max_length=6, blank=True)    # IUOM
    item_supplier      = models.CharField(max_length=6, blank=True)    # ISUPP
    item_department    = models.CharField(max_length=4, blank=True)    # IDEPT
    item_class         = models.CharField(max_length=4, blank=True)    # ICLASS
    item_size          = models.CharField(max_length=3, blank=True)    # ISIZE
    item_color         = models.CharField(max_length=3, blank=True)    # ICOLOR
    item_type          = models.CharField(max_length=1, blank=True)    # ITYPE
    item_tax_code      = models.CharField(max_length=1, blank=True)    # ITAXC
    table_id           = models.CharField(max_length=3, blank=True)    # TABLEID

    # --- Pricing ---
    item_cost          = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ICOST
    item_price         = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IPRICE
    item_discount      = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IDISC
    discount_code      = models.CharField(max_length=3, blank=True)    # IDISCCODE
    item_price_ext     = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IPRICEE
    old_price          = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # OLDPRICE
    price_override     = models.CharField(max_length=3, blank=True)    # PRICEOVER

    # --- Tags / flags ---
    tag1               = models.CharField(max_length=1, blank=True)    # ITAG1
    tag2               = models.CharField(max_length=1, blank=True)    # ITAG2
    tag3               = models.CharField(max_length=1, blank=True)    # ITAG3
    tag4               = models.CharField(max_length=1, blank=True)    # ITAG4
    promo_tag          = models.CharField(max_length=1, blank=True)    # PTAG
    tag                = models.CharField(max_length=1, blank=True)    # TAG

    # --- Row / suspend tracking ---
    transaction_no_ctr  = models.CharField(max_length=8, blank=True)   # TRNBRCTR
    transaction_no_ctr2 = models.CharField(max_length=8, blank=True)   # TRNBRCTR_
    rec_ctr             = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # RECCTR
    rec_num             = models.CharField(max_length=256, blank=True)  # RECNUM

    # --- Service ---
    customer_count      = models.PositiveSmallIntegerField(default=0)  # CUSTCNT (BYTE)
    served_by           = models.CharField(max_length=20, blank=True)  # SERVEBY

    class Meta:
        db_table = 'suspend'
        indexes = [
            models.Index(fields=['table_id']),
            models.Index(fields=['transaction_no', 'rec_ctr']),
            models.Index(fields=['item_code']),
        ]

    def __str__(self):
        return f'{self.transaction_no} / {self.item_code} (held)'


# ---------------------------------------------------------------------------
# POSNCTR  →  Current transaction number counter
# ---------------------------------------------------------------------------

class POSTransCounter(models.Model):
    """
    Equivalent of the Clarion POSNCTR table.
    Single-row table that holds the last-used transaction number string.
    """

    transaction_no = models.CharField(max_length=8)                    # TRNBR

    class Meta:
        db_table = 'posnctr'

    def __str__(self):
        return self.transaction_no


# ---------------------------------------------------------------------------
# POSNBR  →  Transaction number with grand totals
# ---------------------------------------------------------------------------

class POSTransNumber(models.Model):
    """
    Equivalent of the Clarion POSNBR table.
    Tracks the current transaction number alongside running grand totals
    and the previous/current session counters used for Z-reading continuity.
    """

    transaction_no = models.CharField(max_length=8)                    # TRNBR
    grand_tot      = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # GRANDTOT
    grand_tot2     = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # GRANDTOT2
    prev_ctr       = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # PREVCTR
    curr_ctr       = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # CURRCTR

    class Meta:
        db_table = 'posnbr'

    def __str__(self):
        return f'{self.transaction_no} (grand: {self.grand_tot})'


# ---------------------------------------------------------------------------
# OPENMMDD  →  Open terminal / active login tracker
# ---------------------------------------------------------------------------

class OpenTerminal(models.Model):
    """
    Equivalent of the Clarion OPENMMDD table.
    One row per logged-in cashier session per business day per terminal.

    In the old Clarion POS a new physical file was created each day
    (OPEN0214, OPEN0315 …) and its mere existence signalled that the
    store was open.  Here a single table replaces all those files;
    the business_date column carries what the filename used to encode.

    "Is the store open today?" →
        OpenTerminal.objects.filter(
            store_id=store, business_date=today
        ).exists()

    "Who is currently logged in on terminal 001?" →
        OpenTerminal.objects.filter(
            store_id=store, terminal_id='001', business_date=today
        )

    Rows are inserted on cashier login and removed (or soft-closed via
    tag='C') on logout / Z-reading close.
    """

    store_id      = models.CharField(max_length=3)                     # STOREID
    terminal_id   = models.CharField(max_length=3)                     # TERMID
    business_date = models.DateField()                                  # replaces the MMDD in the filename
    user_id       = models.CharField(max_length=10)                    # USERID
    tag           = models.CharField(max_length=1, blank=True)         # TAG  ('C' = closed, blank = open)

    class Meta:
        db_table = 'openterm'
        unique_together = [['store_id', 'terminal_id', 'business_date', 'user_id']]
        indexes = [
            models.Index(fields=['store_id', 'business_date']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f'{self.user_id} @ {self.store_id}/{self.terminal_id} ({self.business_date})'


# ---------------------------------------------------------------------------
# FUNCTIONS  →  Function-key / hotkey mappings
# (will move to settings_app once that app is built)
# ---------------------------------------------------------------------------

class POSFunction(models.Model):
    """
    Equivalent of the Clarion FUNCTIONS table.
    Maps POS function codes to descriptions and keyboard shortcut codes.
    """

    code     = models.CharField(max_length=10)                         # CODE
    desc     = models.CharField(max_length=30, blank=True)             # DESC
    key_code = models.CharField(max_length=2, blank=True)              # KEYCODE

    class Meta:
        db_table = 'functions'

    def __str__(self):
        return f'{self.code} – {self.desc}'


# ---------------------------------------------------------------------------
# COLORS  →  Color code lookup
# (will move to inventory app once that app is built)
# ---------------------------------------------------------------------------

class Color(models.Model):
    """
    Equivalent of the Clarion COLORS table.
    Lookup table of color codes used on item variants.
    Primary key: code. Multi holds a comma-separated alias string.
    """

    code      = models.CharField(max_length=5, unique=True)            # CODE
    color     = models.CharField(max_length=15, blank=True)            # COLOR
    set_value = models.DecimalField(max_digits=10, decimal_places=4, default=0)  # SETVALUE
    multi     = models.CharField(max_length=15, blank=True)            # MULTI

    class Meta:
        db_table = 'colors'

    def __str__(self):
        return f'{self.code} – {self.color}'


# ---------------------------------------------------------------------------
# SIZES  →  Size code lookup
# (will move to inventory app once that app is built)
# ---------------------------------------------------------------------------

class Size(models.Model):
    """
    Equivalent of the Clarion SIZES table.
    Lookup table of size codes used on item variants.
    Primary key: code.
    """

    code      = models.CharField(max_length=3, unique=True)            # CODE
    size      = models.CharField(max_length=4, blank=True)             # SIZE
    set_value = models.DecimalField(max_digits=10, decimal_places=4, default=0)  # SETVALUE

    class Meta:
        db_table = 'sizes'

    def __str__(self):
        return f'{self.code} – {self.size}'


# ---------------------------------------------------------------------------
# ITEMS  →  Product / item master
# (will move to inventory app once that app is built)
# ---------------------------------------------------------------------------

class Item(models.Model):
    """
    Equivalent of the Clarion ITEMS table.
    One row per base item/SKU. Holds all product attributes, pricing
    tiers, stock quantities, and supplier info.
    Primary key: icode.
    """

    # --- Codes ---
    icode       = models.CharField(max_length=15, unique=True)         # ICODE  (primary)
    icode2      = models.CharField(max_length=15, blank=True)          # ICODE2 (alternate code)
    icode3      = models.CharField(max_length=15, blank=True)          # ICODE3 (alternate code)

    # --- Description ---
    long_desc   = models.CharField(max_length=50, blank=True)          # LDESC
    short_desc  = models.CharField(max_length=25, blank=True)          # IDESC

    # --- Classification ---
    department  = models.CharField(max_length=4, blank=True)           # IDEPT
    item_class  = models.CharField(max_length=4, blank=True)           # ICLASS
    category    = models.CharField(max_length=4, blank=True)           # ICAT
    sub_category= models.CharField(max_length=4, blank=True)           # ISUBCAT
    style       = models.CharField(max_length=12, blank=True)          # ISTYLE
    color       = models.CharField(max_length=3, blank=True)           # ICOLOR
    size        = models.CharField(max_length=3, blank=True)           # ISIZE
    item_type   = models.CharField(max_length=1, blank=True)           # ITYPE
    price_type  = models.CharField(max_length=1, blank=True)           # IPTYPE
    tax_code    = models.CharField(max_length=1, blank=True)           # ITAXC
    bar_type    = models.CharField(max_length=1, blank=True)           # IBARTYPE

    # --- Pricing ---
    price       = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPRICE
    price2      = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPRICE2
    price3      = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPRICE3
    price4      = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPRICE4
    cost        = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # ICOST
    in_cost     = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # INCOST
    tax_rate    = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IRATE
    tax_rate3   = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IRATE3

    # --- Discounts ---
    disc1       = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IDISC1
    disc2       = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IDISC2
    disc3       = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IDISC3
    disc4       = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IDISC4
    disc5       = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IDISC5
    disc6       = models.DecimalField(max_digits=10, decimal_places=4, default=0)   # IDISC6
    disc_amt    = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IDISCAMT
    charges     = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # ICHARGES
    markdown    = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IMARKDOWN
    shrink      = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # ISHRINK
    addon       = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # ADDON
    add_amt     = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IADDAMT

    # --- Promo ---
    promo       = models.CharField(max_length=1, blank=True)           # IPROMO
    promo_date1 = models.DateField(null=True, blank=True)              # IPDATE1
    promo_time1 = models.CharField(max_length=5, blank=True)           # IPTIME1
    promo_date2 = models.DateField(null=True, blank=True)              # IPDATE2
    promo_time2 = models.CharField(max_length=5, blank=True)           # IPTIME2

    # --- Unit of measure / packing (primary) ---
    uom         = models.CharField(max_length=6, blank=True)           # IUOM
    pack        = models.CharField(max_length=7, blank=True)           # IPACK
    qty         = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IQTY

    # --- Unit of measure / packing (secondary) ---
    uom2        = models.CharField(max_length=6, blank=True)           # IUOM2
    pack2       = models.CharField(max_length=7, blank=True)           # IPACK2
    qty2        = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IQTY2

    # --- Supplier / ordering ---
    supplier    = models.CharField(max_length=6, blank=True)           # ISUPP
    min_order   = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IMINORDER
    po_qty      = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPOQTY
    last_order  = models.DateField(null=True, blank=True)              # LORDER
    po_no       = models.CharField(max_length=8, blank=True)           # PONO

    # --- Stock ---
    has_inventory = models.CharField(max_length=1, blank=True)         # IINVENT
    stocks        = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ISTOCKS
    stocks2       = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ISTOCKS2
    qty_min       = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IQMIN
    qty_max       = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IQMAX
    warehouse_qty = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IWQTY
    beg_bal1      = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # BEGBAL1
    beg_bal2      = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # BEGBAL2
    beg_cost      = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # BEGCOST
    last_sold     = models.DateField(null=True, blank=True)            # LSOLD

    # --- Flags ---
    inactive      = models.CharField(max_length=1, blank=True)         # INACTIVE
    is_serial     = models.CharField(max_length=1, blank=True)         # ISERIAL
    is_generic    = models.CharField(max_length=1, blank=True)         # IGENERIC
    is_alias      = models.CharField(max_length=1, blank=True)         # IALIAS
    tag           = models.CharField(max_length=1, blank=True)         # ITAG

    # --- Accounting ---
    gl_code       = models.CharField(max_length=4, blank=True)         # GLCODE
    inv_code      = models.CharField(max_length=4, blank=True)         # INVCODE

    # --- Audit ---
    date_created  = models.DateField(null=True, blank=True)            # DCREATED

    class Meta:
        db_table = 'items'
        indexes = [
            models.Index(fields=['long_desc']),
            models.Index(fields=['short_desc']),
        ]

    def __str__(self):
        return f'{self.icode} – {self.short_desc}'


# ---------------------------------------------------------------------------
# ITEMDTL  →  Item variant detail (size + color + barcode)
# (will move to inventory app once that app is built)
# ---------------------------------------------------------------------------

class ItemDetail(models.Model):
    """
    Equivalent of the Clarion ITEMDTL table.
    One row per item/color/size combination. Holds the variant-level
    barcode, stock, cost, and price.
    Primary key: barcode. Foreign key: icode → Item.
    """

    icode    = models.CharField(max_length=15)                         # ICODE  (FK to Item)
    color    = models.CharField(max_length=3, blank=True)              # COLOR
    size     = models.CharField(max_length=3, blank=True)              # SIZE
    stocks1  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ISTOCKS1
    stocks2  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ISTOCKS2
    cost     = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # ICOST
    price    = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # IPRICE
    min_qty  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # MIN
    max_qty  = models.DecimalField(max_digits=15, decimal_places=4, default=0)  # MAX
    barcode  = models.CharField(max_length=15, unique=True)            # BARCODE (primary key in Clarion)
    multi    = models.CharField(max_length=15, blank=True)             # MULTI

    class Meta:
        db_table = 'itemdtl'
        indexes = [
            models.Index(fields=['icode']),
            models.Index(fields=['icode', 'color']),
            models.Index(fields=['icode', 'size']),
        ]

    def __str__(self):
        return f'{self.barcode} – {self.icode} {self.color}/{self.size}'


# ---------------------------------------------------------------------------
# ITEMLINK  →  Linked / bundled items
# (will move to inventory app once that app is built)
# ---------------------------------------------------------------------------

class ItemLink(models.Model):
    """
    Equivalent of the Clarion ITEMLINK table.
    Links one item to another (e.g. a bundle or accessory).
    Composite primary key: (icode, linkcode).
    """

    icode     = models.CharField(max_length=15)                        # ICODE     (FK to Item)
    link_code = models.CharField(max_length=15)                        # LINKCODE  (FK to linked Item)
    desc      = models.CharField(max_length=25, blank=True)            # IDESC
    price     = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPRICE
    price2    = models.DecimalField(max_digits=15, decimal_places=4, default=0)   # IPRICE2

    class Meta:
        db_table = 'itemlink'
        unique_together = [['icode', 'link_code']]
        indexes = [
            models.Index(fields=['icode']),
        ]

    def __str__(self):
        return f'{self.icode} → {self.link_code}'


# ---------------------------------------------------------------------------
# Transaction Logs Payment / tender lines
# ---------------------------------------------------------------------------

# Note: In the old Clarion POS, payment lines were stored in the same file as the cart lines (TEMPTRANS), with item_code='PAYMENT' and the tender code in the discount_code field.  Here we split them into a separate Payments table for better data integrity and easier querying.
class Payment(models.Model):
    """
    Payment lines. One transaction can have multiple tender types
    (e.g. partial cash + card split). Linked to TransactionHeader,
    not to individual items.
    """
    header = models.ForeignKey(
        TransactionHeader,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    pcode             = models.CharField(max_length=3)
    amount            = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    tender_desc       = models.CharField(max_length=15, blank=True)
    # holder            = models.CharField(max_length=50, null=True)
    payment_reference = models.CharField(max_length=20, null=True)

    class Meta:
        db_table = 'payment'
        indexes = [
            models.Index(fields=['header']),
        ]

    def __str__(self):
        return f'{self.header.transaction_no} – {self.pcode} {self.amount}'
    

# Note: Transaction Payment / Tender counts for Z-reading continuity tracking.  Updated on each transaction close.
class TransactionTenderCount(models.Model):
    """
    Tracks the count of each tender type used in a transaction, for Z-reading continuity.
    One row per transaction per tender type.
    """

    transaction_no = models.CharField(max_length=8)                # TRNBR (FK to TransactionLog)
    pcode          = models.CharField(max_length=3)                # PCODE (FK to Tender)
    count          = models.PositiveIntegerField(default=0)        # COUNT

    class Meta:
        db_table = 'transaction_tender_counts'
        unique_together = [['transaction_no', 'pcode']]
        indexes = [
            models.Index(fields=['transaction_no']),
        ]

    def __str__(self):
        return f'{self.transaction_no} – {self.pcode} count: {self.count}'


# ---------------------------------------------------------------------------
# For Checking Terminal Setup and Configuration
# ---------------------------------------------------------------------------
class TerminalConfiguration(models.Model):

    CONNECTION_TYPES = [
        ("SERIAL","Serial"),
        ("USB","USB"),
        ("NETWORK","Network"),
    ]
    store_id = models.CharField(max_length=3)
    terminal_id = models.CharField(max_length=3)
    store_name = models.CharField(max_length=50, blank=True)
    branch_name = models.CharField(max_length=20, blank=True)
    vat = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    print_in = models.CharField(max_length=10, choices=CONNECTION_TYPES, default="SERIAL")
    open_time = models.TimeField(default=datetime.time(9,0))
    cutoff_time = models.TimeField(default=datetime.time(4,0))

    class Meta:
        db_table = "terminal_configurations"
        unique_together = [["store_id","terminal_id"]]

    def __str__(self):
        return f"{self.store_id}/{self.terminal_id}"

class TerminalReceiptHeader(models.Model):

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="headers"
    )

    line_number = models.PositiveSmallIntegerField()
    header_text = models.CharField(max_length=40)
    is_capitalized = models.BooleanField(default=False)

    class Meta:
        db_table = "terminal_receipt_headers"
        ordering = ["line_number"]

class TerminalReceiptFooter(models.Model):

    FOOTER_TYPE_CHOICES = [
        ("customer", "Customer Copy"),
        ("record", "Record Copy"),
        ("both", "Both Copies"),
    ]

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="footers"
    )

    footer_type = models.CharField(
        max_length=10,
        choices=FOOTER_TYPE_CHOICES,
        default="customer"
    )

    line_number = models.PositiveSmallIntegerField()
    footer_text = models.CharField(max_length=40)
    is_centered = models.BooleanField(default=False)
    is_left_align = models.BooleanField(default=False)

    class Meta:
        db_table = "terminal_receipt_footers"
        ordering = ["line_number"]


class TerminalPort(models.Model):

    PORT_TYPES = [
        ("PRINTER","Printer"),
        ("DRAWER","Cash Drawer"),
        ("DISPLAY","Pole Display"),
    ]

    CONNECTION_TYPES = [
        ("SERIAL","Serial"),
        ("USB","USB"),
        ("NETWORK","Network"),
        ("WINDOWS","Windows"),
    ]

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="ports"
    )

    port_type = models.CharField(max_length=10, choices=PORT_TYPES)
    connection_type = models.CharField(max_length=10, choices=CONNECTION_TYPES)
    
    # General field (existing)
    port_name = models.CharField(max_length=50, blank=True, null=True)

    # New fields for multi-connection support
    baudrate = models.IntegerField(blank=True, null=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)
    port_no = models.IntegerField(blank=True, null=True)
    printer_name = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "terminal_ports"


class TerminalDisplayCode(models.Model):

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="display_codes"
    )

    code_group = models.CharField(max_length=2)
    code_value = models.CharField(max_length=5, blank=True)
    code_length = models.CharField(max_length=2, blank=True)

    class Meta:
        db_table = "terminal_display_codes"
