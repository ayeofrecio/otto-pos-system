
import csv
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from sales.models import Item, ItemDetail


class Command(BaseCommand):
    help = "Seed Items and ItemDetails from TXT files"

    def add_arguments(self, parser):
        parser.add_argument('--items', type=str, required=True)
        parser.add_argument('--itemdtl', type=str, required=True)
        parser.add_argument('--itemscosts', type=str, required=True)

    def handle(self, *args, **options):
        items_file = options['items']
        itemdtl_file = options['itemdtl']
        itemscosts_file = options['itemscosts']

        with transaction.atomic():
            self.load_items(items_file)
            self.load_item_details(itemdtl_file)
            self.load_items_costs(itemscosts_file)
            
        self.stdout.write(self.style.SUCCESS("Seeding completed."))

    def clean_code(self, value):
        """
        Extract code before dash: '5-OTHER' -> '5'
        """
        return value.split('-')[0] if value else ''

    def load_items(self, filepath):
        self.stdout.write(f"Loading Items from {filepath}...")

        with open(filepath, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=',')

            items_to_create = []

            for row in reader:
                if row.get("ACTIVE") != "1":
                    continue

                item = Item(
                    icode=row["STOCKNO"].strip(),
                    short_desc=row["STOCKNAME"].strip(),
                    long_desc=row["STOCKDESC"].strip(),

                    department=self.clean_code(row.get("DEPT", "")),
                    item_class=self.clean_code(row.get("CLASS", "")),
                    category=self.clean_code(row.get("CATEGORY", "")),

                    uom=row.get("UOM", "").strip(),
                    item_type=self.clean_code(row.get("TYPE", "")),

                    inactive='0',
                )

                items_to_create.append(item)

            Item.objects.bulk_create(items_to_create, ignore_conflicts=True)

        self.stdout.write(f"{len(items_to_create)} Items loaded.")

    def load_item_details(self, filepath):
        self.stdout.write(f"Loading ItemDetails from {filepath}...")

        with open(filepath, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=',')

            details_to_create = []

            for row in reader:
                if row.get("ACTIVE") != "1":
                    continue

                detail = ItemDetail(
                    icode=row["STOCKNO"].strip(),
                    barcode=row["BARCODE"].strip(),
                    color=row.get("COLOR_CODE", "").strip(),
                    size=row.get("SIZE_DESC", "").strip(),

                    stocks1=Decimal("0"),
                    stocks2=Decimal("0"),
                    cost=Decimal("0"),
                    price=Decimal("0"),
                    min_qty=Decimal("0"),
                    max_qty=Decimal("0"),
                )

                details_to_create.append(detail)

            ItemDetail.objects.bulk_create(details_to_create, ignore_conflicts=True)

        self.stdout.write(f"{len(details_to_create)} ItemDetails loaded.")


    def load_items_costs(self, filepath):
        self.stdout.write(f"Loading Items Costs from {filepath}...")

        updated_count = 0

        with open(filepath, newline='', encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter=',')

            for row in reader:
                stockno = row.get("STOCKNO", "").strip()
                cost_val = row.get("COST", "").strip()

                if not stockno or not cost_val:
                    continue

                try:
                    cost = Decimal(cost_val)
                except:
                    continue

                updated = Item.objects.filter(icode=stockno).update(price=cost)

                if updated:
                    updated_count += 1

        self.stdout.write(f"{updated_count} Items updated.")