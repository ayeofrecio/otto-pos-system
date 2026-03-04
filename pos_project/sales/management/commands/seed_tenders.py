"""
Seed default tenders (payment methods) for POS.
Run: python manage.py seed_tenders
"""

from django.core.management.base import BaseCommand

from sales.models import Tender


class Command(BaseCommand):
    help = "Add default payment tenders (Cash, Card, GCash, etc.)"

    def handle(self, *args, **options):
        tenders_data = [
            ("P01", "CASH", "Cash", "Y"),      # pallow=Y
            ("P02", "CARD", "Card", "Y"),
            ("P03", "GCASH", "GCash", "Y"),
            ("P04", "MAYA", "Maya", "Y"),
        ]
        for pcode, key_name, description, pallow in tenders_data:
            _, created = Tender.objects.get_or_create(
                pcode=pcode,
                defaults={
                    "key_name": key_name,
                    "description": description,
                    "pallow": pallow,
                    "pchange": "Y" if pcode == "P01" else "",  # Cash gives change
                },
            )
            if created:
                self.stdout.write(f"Created tender: {pcode} - {description}")

        self.stdout.write(self.style.SUCCESS("Done. Tenders available for payment."))
