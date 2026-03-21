"""
Seed sample items for POS testing.
Run: python manage.py seed_sample_items
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from sales.models import Item, ItemDetail


class Command(BaseCommand):
    help = "Add sample items and barcodes for POS testing"

    def handle(self, *args, **options):
        items_data = [
            ("SHOE001", "Nike Air Max", "Running shoe", Decimal("4500.00")),
            ("SHOE002", "Adidas Ultraboost", "Running shoe", Decimal("5200.00")),
            ("SHOE003", "Converse Chuck Taylor", "Canvas sneaker", Decimal("2800.00")),
        ]
        for icode, short_desc, long_desc, price in items_data:
            item, created = Item.objects.get_or_create(
                icode=icode,
                defaults={
                    "short_desc": short_desc,
                    "long_desc": long_desc,
                    "price": price,
                },
            )
            if created:
                self.stdout.write(f"Created item: {icode} - {short_desc}")

        # Add barcodes (ItemDetail) - barcode scanner looks up by barcode
        barcodes = [
            ("8901234567890", "SHOE001", "9", "BLK"),   # Nike Air Max, Size 9, Black
            ("8901234567891", "SHOE001", "10", "BLK"),  # Nike Air Max, Size 10, Black
            ("8901234567892", "SHOE002", "9", "WHT"),   # Adidas, Size 9, White
            ("8901234567893", "SHOE003", "8", "RED"),   # Converse, Size 8, Red
        ]
        for barcode, icode, size, color in barcodes:
            item = Item.objects.get(icode=icode)
            _, created = ItemDetail.objects.get_or_create(
                barcode=barcode,
                defaults={
                    "icode": icode,
                    "size": size,
                    "color": color,
                    "price": item.price,
                },
            )
            if created:
                self.stdout.write(f"Created barcode: {barcode} -> {icode} ({size}/{color})")

        self.stdout.write(self.style.SUCCESS("Done. You can scan these barcodes:"))
        self.stdout.write("  8901234567890 - Nike Air Max Size 9 Black")
        self.stdout.write("  8901234567891 - Nike Air Max Size 10 Black")
        self.stdout.write("  8901234567892 - Adidas Ultraboost Size 9 White")
        self.stdout.write("  8901234567891 - Converse Chuck Taylor Size 8 Red")
        self.stdout.write("  Or type: SHOE001, SHOE002, SHOE003 (item codes)")
