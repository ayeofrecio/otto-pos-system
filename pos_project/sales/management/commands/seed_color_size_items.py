"""
Seed Color, Size, Item, and ItemDetail tables with sample apparel data.

Run:
    python manage.py seed_color_size_items
    python manage.py seed_color_size_items --clear   (wipe seeded records first)
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from sales.models import Color, Item, ItemDetail, Size


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

COLORS = [
    # (code, description)
    ("BLK", "Black"),
    ("WHT", "White"),
    ("RED", "Red"),
    ("NVY", "Navy"),
    ("GRY", "Gray"),
    ("BLU", "Blue"),
]

SIZES = [
    # (code, description)
    ("S",   "S"),
    ("M",   "M"),
    ("L",   "L"),
    ("XL",  "XL"),
    ("2XL", "2XL"),
    ("7",   "7"),
    ("8",   "8"),
    ("9",   "9"),
    ("10",  "10"),
    ("11",  "11"),
]

# Each item is (icode, short_desc, long_desc, base_price, is_alias)
# is_alias = "Y" means it has color/size variants selected via picker modal
ITEMS = [
    ("TSH001", "Basic Tee",         "Basic Cotton T-Shirt",     Decimal("350.00"),  "Y"),
    ("JNS001", "Slim Jeans",        "Slim-Fit Denim Jeans",     Decimal("1200.00"), "Y"),
    ("SNK001", "Classic Sneaker",   "Classic Canvas Sneaker",   Decimal("2500.00"), "Y"),
]

# ItemDetail variants: (barcode, icode, color_code, size_code, price)
# Barcode format: up to 15 chars — we use a readable scheme here.
# For the 12-char "embedded" format barcode[-4:-2]=color_code, barcode[-2:]=size_code
# the backend also accepts plain barcodes looked up from itemdtl.
VARIANTS = [
    # --- Basic Tee (TSH001) ---
    ("TSH001BLKS",  "TSH001", "BLK", "S",   Decimal("350.00")),
    ("TSH001BLKM",  "TSH001", "BLK", "M",   Decimal("350.00")),
    ("TSH001BLKL",  "TSH001", "BLK", "L",   Decimal("350.00")),
    ("TSH001BLKXL", "TSH001", "BLK", "XL",  Decimal("350.00")),
    ("TSH001WHTS",  "TSH001", "WHT", "S",   Decimal("350.00")),
    ("TSH001WHTM",  "TSH001", "WHT", "M",   Decimal("350.00")),
    ("TSH001WHTL",  "TSH001", "WHT", "L",   Decimal("350.00")),
    ("TSH001REDS",  "TSH001", "RED", "S",   Decimal("350.00")),
    ("TSH001REDM",  "TSH001", "RED", "M",   Decimal("350.00")),
    ("TSH001REDL",  "TSH001", "RED", "L",   Decimal("350.00")),
    # --- Slim Jeans (JNS001) ---
    ("JNS001BLKS",  "JNS001", "BLK", "S",   Decimal("1200.00")),
    ("JNS001BLKM",  "JNS001", "BLK", "M",   Decimal("1200.00")),
    ("JNS001BLKL",  "JNS001", "BLK", "L",   Decimal("1200.00")),
    ("JNS001NVYS",  "JNS001", "NVY", "S",   Decimal("1200.00")),
    ("JNS001NVYM",  "JNS001", "NVY", "M",   Decimal("1200.00")),
    ("JNS001NVYL",  "JNS001", "NVY", "L",   Decimal("1200.00")),
    ("JNS001GRYS",  "JNS001", "GRY", "S",   Decimal("1200.00")),
    ("JNS001GRYM",  "JNS001", "GRY", "M",   Decimal("1200.00")),
    # --- Classic Sneaker (SNK001) ---
    ("SNK001BLK7",  "SNK001", "BLK", "7",   Decimal("2500.00")),
    ("SNK001BLK8",  "SNK001", "BLK", "8",   Decimal("2500.00")),
    ("SNK001BLK9",  "SNK001", "BLK", "9",   Decimal("2500.00")),
    ("SNK001BLK10", "SNK001", "BLK", "10",  Decimal("2500.00")),
    ("SNK001WHT7",  "SNK001", "WHT", "7",   Decimal("2500.00")),
    ("SNK001WHT8",  "SNK001", "WHT", "8",   Decimal("2500.00")),
    ("SNK001WHT9",  "SNK001", "WHT", "9",   Decimal("2500.00")),
    ("SNK001RED8",  "SNK001", "RED", "8",   Decimal("2500.00")),
    ("SNK001RED9",  "SNK001", "RED", "9",   Decimal("2500.00")),
    ("SNK001BLU9",  "SNK001", "BLU", "9",   Decimal("2500.00")),
]

# Seeded icode values — used for --clear
SEEDED_ICODES = [i[0] for i in ITEMS]
SEEDED_BARCODES = [v[0] for v in VARIANTS]
SEEDED_COLORS = [c[0] for c in COLORS]
SEEDED_SIZES = [s[0] for s in SIZES]


class Command(BaseCommand):
    help = "Seed Color, Size, Item, and ItemDetail tables with sample apparel data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete seeded records before re-inserting",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear()

        created_colors   = self._seed_colors()
        created_sizes    = self._seed_sizes()
        created_items    = self._seed_items()
        created_variants = self._seed_variants()

        self.stdout.write(self.style.SUCCESS(
            f"\nDone.  Colors: {created_colors}  Sizes: {created_sizes}  "
            f"Items: {created_items}  Variants: {created_variants}"
        ))
        self._print_summary()

    # ------------------------------------------------------------------
    def _clear(self):
        deleted_v, _ = ItemDetail.objects.filter(barcode__in=SEEDED_BARCODES).delete()
        deleted_i, _ = Item.objects.filter(icode__in=SEEDED_ICODES).delete()
        deleted_c, _ = Color.objects.filter(code__in=SEEDED_COLORS).delete()
        deleted_s, _ = Size.objects.filter(code__in=SEEDED_SIZES).delete()
        self.stdout.write(
            f"Cleared: {deleted_v} variants, {deleted_i} items, "
            f"{deleted_c} colors, {deleted_s} sizes"
        )

    def _seed_colors(self):
        count = 0
        for code, description in COLORS:
            _, created = Color.objects.get_or_create(
                code=code,
                defaults={"color": description},
            )
            if created:
                self.stdout.write(f"  Color  + {code}  {description}")
                count += 1
            else:
                self.stdout.write(f"  Color  = {code}  (already exists)")
        return count

    def _seed_sizes(self):
        count = 0
        for code, description in SIZES:
            _, created = Size.objects.get_or_create(
                code=code,
                defaults={"size": description},
            )
            if created:
                self.stdout.write(f"  Size   + {code}  {description}")
                count += 1
            else:
                self.stdout.write(f"  Size   = {code}  (already exists)")
        return count

    def _seed_items(self):
        count = 0
        for icode, short_desc, long_desc, price, is_alias in ITEMS:
            _, created = Item.objects.get_or_create(
                icode=icode,
                defaults={
                    "short_desc": short_desc,
                    "long_desc":  long_desc,
                    "price":      price,
                    "is_alias":   is_alias,
                },
            )
            if created:
                self.stdout.write(f"  Item   + {icode}  {short_desc}")
                count += 1
            else:
                self.stdout.write(f"  Item   = {icode}  (already exists)")
        return count

    def _seed_variants(self):
        count = 0
        for barcode, icode, color_code, size_code, price in VARIANTS:
            _, created = ItemDetail.objects.get_or_create(
                barcode=barcode,
                defaults={
                    "icode": icode,
                    "color": color_code,
                    "size":  size_code,
                    "price": price,
                },
            )
            if created:
                self.stdout.write(
                    f"  Variant+ {barcode:<15}  {icode}  {color_code}/{size_code}"
                )
                count += 1
            else:
                self.stdout.write(f"  Variant= {barcode:<15}  (already exists)")
        return count

    def _print_summary(self):
        self.stdout.write("\nScan any barcode below, or type the icode to get the picker:")
        self.stdout.write(f"  {'ICODE':<10} {'BARCODE':<16} {'COLOR':<6} {'SIZE'}")
        self.stdout.write("  " + "-" * 46)
        for barcode, icode, color_code, size_code, price in VARIANTS:
            self.stdout.write(
                f"  {icode:<10} {barcode:<16} {color_code:<6} {size_code}"
            )
        self.stdout.write(
            "\nAlias icodes (trigger color/size picker on Enter): "
            + ", ".join(SEEDED_ICODES)
        )
