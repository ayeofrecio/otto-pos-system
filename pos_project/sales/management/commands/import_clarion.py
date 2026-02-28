"""
Management command: import_clarion

Loads historical Clarion CSV exports into the Django database.
Safe to re-run — already-imported rows are skipped, not duplicated.

Usage
-----
    # Import TLOG (TransactionLog)
    python manage.py import_clarion --source tlog --file path/to/tlog_export.csv

    # Import ACCT (AccountingSummary)
    python manage.py import_clarion --source acct --file path/to/acct_export.csv

    # Dry-run (validate CSV without writing to DB)
    python manage.py import_clarion --source tlog --file tlog.csv --dry-run

    # Show progress every N rows (default: 500)
    python manage.py import_clarion --source tlog --file tlog.csv --batch-size 1000

CSV Format
----------
The CSV must have a header row.  Column names must match the Clarion field
names listed in each FIELD_MAP below (case-insensitive).
Export from Clarion using the standard "Export to CSV" option in each
table's browse window, or export using a Clarion FILESHARE utility.

Rules Applied
-------------
- transaction_no values are prefixed with "CLR-" to prevent collision with
  new POS transaction numbers.
- Imported rows are read-only by convention (no POSSession link, no void
  logic applies to them).
- Duplicate detection:
    TLOG : (store_id, terminal_id, transaction_no, item_code) — skipped if exists
    ACCT : (store_id, terminal_id, transaction_date, user_id) — skipped if exists
"""

import csv
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import AccountingSummary, TransactionLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field maps  {csv_column_name: django_field_name}
# Keys are uppercase Clarion names; values are Django model field names.
# ---------------------------------------------------------------------------

TLOG_FIELD_MAP = {
    'USERID':    'user_id',
    'USERID2':   'user_id2',
    'TERMID':    'terminal_id',
    'STOREID':   'store_id',
    'TRNBR':     'transaction_no',       # will be prefixed with CLR-
    'TRDATE':    'transaction_date',
    'TRDATER':   'transaction_date_r',
    'TRTIME':    'transaction_time',
    'TRTYPE':    'transaction_type',
    'RCODE':     'return_code',
    'TRREF1':    'item_ref',
    'ITEMCODE':  'item_code',
    'IDESC':     'item_description',
    'IQTY':      'item_qty',
    'IUOM':      'item_uom',
    'ISUPP':     'item_supplier',
    'IDEPT':     'item_department',
    'ICLASS':    'item_class',
    'ISIZE':     'item_size',
    'ICOLOR':    'item_color',
    'ITYPE':     'item_type',
    'ICOST':     'item_cost',
    'IPRICE':    'item_price',
    'IDISC':     'item_discount',
    'IDISCCODE': 'discount_code',
    'IPRICEE':   'item_price_ext',
    'ITAG1':     'tag1',
    'ITAG2':     'tag2',
    'ITAG3':     'tag3',
    'ITAG4':     'tag4',
    'PTAG':      'promo_tag',
    'TABLEID':   'table_id',
    'SERVEBY':   'served_by',
    'CUSTCNT':   'customer_count',
}

ACCT_FIELD_MAP = {
    'STOREID':   'store_id',
    'TERMID':    'terminal_id',
    'TRDATE':    'transaction_date',
    'USERID':    'user_id',
    'ISOLD':     'items_sold',
    'CUSTCNT':   'customer_count',
    'IRETCNT':   'return_count',
    'IRETTOT':   'return_total',
    'IVOIDCNT':  'void_item_count',
    'IVOIDTOT':  'void_item_total',
    'TRVPRVCNT': 'void_prev_count',
    'TRVPRVTOT': 'void_prev_total',
    'TRVOIDCNT': 'void_trans_count',
    'TRVOIDTOT': 'void_trans_total',
    'IDISCCNT':  'item_disc_count',
    'IDISCTOT':  'item_disc_total',
    'IDISCACNT': 'item_disc_a_count',
    'IDISCATOT': 'item_disc_a_total',
    'TDISCCNT':  'trans_disc_count',
    'TDISCTOT':  'trans_disc_total',
    'TDISCACNT': 'trans_disc_a_count',
    'TDISCATOT': 'trans_disc_a_total',
    'WITHDCNT':  'withdrawal_count',
    'WITHDTOT':  'withdrawal_total',
    'FTRNBR':    'first_trans_no',
    'LTRNBR':    'last_trans_no',
    'XREADING':  'x_reading',
    'ZREADING':  'z_reading',
    'OLDTOTAL':  'old_total',
    'NEWTOTAL':  'new_total',
    'P01CNT': 'p01_count', 'P01TTL': 'p01_total',
    'P02CNT': 'p02_count', 'P02TTL': 'p02_total',
    'P03CNT': 'p03_count', 'P03TTL': 'p03_total',
    'P04CNT': 'p04_count', 'P04TTL': 'p04_total',
    'P05CNT': 'p05_count', 'P05TTL': 'p05_total',
    'P06CNT': 'p06_count', 'P06TTL': 'p06_total',
    'P07CNT': 'p07_count', 'P07TTL': 'p07_total',
    'P08CNT': 'p08_count', 'P08TTL': 'p08_total',
    'P09CNT': 'p09_count', 'P09TTL': 'p09_total',
    'P10CNT': 'p10_count', 'P10TTL': 'p10_total',
    'P11CNT': 'p11_count', 'P11TTL': 'p11_total',
    'P12CNT': 'p12_count', 'P12TTL': 'p12_total',
    'P13CNT': 'p13_count', 'P13TTL': 'p13_total',
    'P14CNT': 'p14_count', 'P14TTL': 'p14_total',
    'P15CNT': 'p15_count', 'P15TTL': 'p15_total',
    'P16CNT': 'p16_count', 'P16TTL': 'p16_total',
    'P17CNT': 'p17_count', 'P17TTL': 'p17_total',
    'P18CNT': 'p18_count', 'P18TTL': 'p18_total',
    'P19CNT': 'p19_count', 'P19TTL': 'p19_total',
    'P20CNT': 'p20_count', 'P20TTL': 'p20_total',
    'P21CNT': 'p21_count', 'P21TTL': 'p21_total',
    'P22CNT': 'p22_count', 'P22TTL': 'p22_total',
    'P23CNT': 'p23_count', 'P23TTL': 'p23_total',
    'P24CNT': 'p24_count', 'P24TTL': 'p24_total',
    'NONVAT':  'non_vat',
    'VATABLE':  'vatable',
}

# ---------------------------------------------------------------------------
# Field type helpers
# ---------------------------------------------------------------------------

DATE_FIELDS = {
    'transaction_date', 'transaction_date_r',
}

DECIMAL_FIELDS = (
    {
        'item_qty', 'item_cost', 'item_price', 'item_discount', 'item_price_ext',
        'items_sold', 'customer_count',
        'return_count', 'return_total',
        'void_item_count', 'void_item_total',
        'void_prev_count', 'void_prev_total',
        'void_trans_count', 'void_trans_total',
        'item_disc_count', 'item_disc_total', 'item_disc_a_count', 'item_disc_a_total',
        'trans_disc_count', 'trans_disc_total', 'trans_disc_a_count', 'trans_disc_a_total',
        'withdrawal_count', 'withdrawal_total',
        'x_reading', 'z_reading', 'old_total', 'new_total',
        'non_vat', 'vatable',
    }
    | {f'p{n:02d}_count' for n in range(1, 25)}
    | {f'p{n:02d}_total' for n in range(1, 25)}
)


def _parse_date(value: str):
    """Parse a date string in common Clarion formats. Returns None on blank/invalid."""
    value = value.strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d'):
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> Decimal:
    """Parse a decimal string. Returns Decimal('0') on blank/invalid."""
    value = value.strip().replace(',', '')
    if not value:
        return Decimal('0')
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal('0')


def _map_row(raw_row: dict, field_map: dict, errors: list, line_no: int) -> dict:
    """
    Convert a raw CSV row dict (Clarion column names) to a Django field dict.
    Unknown CSV columns are silently ignored.
    """
    result = {}
    upper_row = {k.strip().upper(): v for k, v in raw_row.items()}

    for clarion_col, django_field in field_map.items():
        raw_value = upper_row.get(clarion_col, '').strip()

        if django_field in DATE_FIELDS:
            parsed = _parse_date(raw_value)
            if raw_value and parsed is None:
                errors.append(f"Line {line_no}: cannot parse date '{raw_value}' for {clarion_col}")
            result[django_field] = parsed

        elif django_field in DECIMAL_FIELDS:
            result[django_field] = _parse_decimal(raw_value)

        else:
            result[django_field] = raw_value

    return result


# ---------------------------------------------------------------------------
# Source-specific importers
# ---------------------------------------------------------------------------

class _TlogImporter:
    model = TransactionLog
    field_map = TLOG_FIELD_MAP
    label = 'TLOG'

    @staticmethod
    def build_key(row: dict) -> tuple:
        return (
            row.get('store_id', ''),
            row.get('terminal_id', ''),
            row.get('transaction_no', ''),
            row.get('item_code', ''),
        )

    @staticmethod
    def exists(row: dict) -> bool:
        return TransactionLog.objects.filter(
            store_id=row['store_id'],
            terminal_id=row['terminal_id'],
            transaction_no=row['transaction_no'],
            item_code=row.get('item_code', ''),
        ).exists()

    @staticmethod
    def prefix_transaction_no(row: dict) -> dict:
        trnbr = row.get('transaction_no', '')
        if trnbr and not trnbr.startswith('CLR-'):
            row['transaction_no'] = f'CLR-{trnbr}'
        return row

    def create(self, row: dict):
        row = self.prefix_transaction_no(row)
        return TransactionLog(**row)


class _AcctImporter:
    model = AccountingSummary
    field_map = ACCT_FIELD_MAP
    label = 'ACCT'

    @staticmethod
    def build_key(row: dict) -> tuple:
        return (
            row.get('store_id', ''),
            row.get('terminal_id', ''),
            str(row.get('transaction_date', '')),
            row.get('user_id', ''),
        )

    @staticmethod
    def exists(row: dict) -> bool:
        return AccountingSummary.objects.filter(
            store_id=row['store_id'],
            terminal_id=row['terminal_id'],
            transaction_date=row['transaction_date'],
            user_id=row['user_id'],
        ).exists()

    def create(self, row: dict):
        return AccountingSummary(**row)


IMPORTERS = {
    'tlog': _TlogImporter(),
    'acct': _AcctImporter(),
}

# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        'Import historical Clarion CSV exports into the Django database.\n'
        'Sources: tlog, acct\n'
        'Example: python manage.py import_clarion --source tlog --file tlog_export.csv'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            required=True,
            choices=list(IMPORTERS.keys()),
            help='Which Clarion table to import: tlog or acct',
        )
        parser.add_argument(
            '--file',
            required=True,
            help='Path to the CSV export file',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Number of rows per bulk_create batch (default: 500)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Validate the CSV without writing anything to the database',
        )
        parser.add_argument(
            '--encoding',
            default='utf-8-sig',
            help='CSV file encoding (default: utf-8-sig, handles Excel BOM)',
        )

    def handle(self, *args, **options):
        source = options['source']
        csv_path = Path(options['file'])
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        encoding = options['encoding']

        if not csv_path.exists():
            raise CommandError(f'File not found: {csv_path}')

        importer = IMPORTERS[source]

        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN — no data will be written'))

        self.stdout.write(f'Importing {importer.label} from {csv_path} ...')

        total = skipped = created = error_count = 0
        parse_errors = []
        batch = []

        with open(csv_path, newline='', encoding=encoding) as fh:
            reader = csv.DictReader(fh)

            for line_no, raw_row in enumerate(reader, start=2):
                total += 1
                mapped = _map_row(raw_row, importer.field_map, parse_errors, line_no)

                # Skip rows where required keys are blank
                if not mapped.get('store_id') or not mapped.get('terminal_id'):
                    skipped += 1
                    continue

                # Skip duplicates
                if importer.exists(mapped):
                    skipped += 1
                    continue

                obj = importer.create(mapped)
                batch.append(obj)

                if len(batch) >= batch_size:
                    if not dry_run:
                        with transaction.atomic():
                            importer.model.objects.bulk_create(batch, ignore_conflicts=True)
                    created += len(batch)
                    batch = []
                    self.stdout.write(f'  ... {created} rows written', ending='\r')
                    self.stdout.flush()

        # Final batch
        if batch:
            if not dry_run:
                with transaction.atomic():
                    importer.model.objects.bulk_create(batch, ignore_conflicts=True)
            created += len(batch)

        # Report parse errors (non-fatal)
        if parse_errors:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'{len(parse_errors)} parse warning(s):'))
            for msg in parse_errors[:20]:
                self.stdout.write(f'  {msg}')
            if len(parse_errors) > 20:
                self.stdout.write(f'  ... and {len(parse_errors) - 20} more (check logs)')
            error_count = len(parse_errors)

        self.stdout.write('')
        mode = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}Done. '
                f'Total rows read: {total} | '
                f'Created: {created} | '
                f'Skipped (duplicate/blank): {skipped} | '
                f'Parse warnings: {error_count}'
            )
        )
        logger.info(
            'import_clarion %s: total=%d created=%d skipped=%d warnings=%d dry_run=%s',
            source, total, created, skipped, error_count, dry_run,
        )
