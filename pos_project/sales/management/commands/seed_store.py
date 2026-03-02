"""
Seed store/terminal setup (TerminalSetup) with store name and details.
Run: python manage.py seed_store
"""

from django.core.management.base import BaseCommand

from sales.models import TerminalSetup


class Command(BaseCommand):
    help = "Add default store/terminal setup with store name"

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default="My Shoe Store",
            help="Store name (default: My Shoe Store)",
        )

    def handle(self, *args, **options):
        store_name = options["name"]
        setup, created = TerminalSetup.objects.get_or_create(
            store_id="001",
            terminal_id="001",
            defaults={
                "header01": store_name,
                "header02": "Thank you for your purchase!",
                "header03": "",
                "footer01": "Please come again",
                "footer02": "",
            },
        )
        if not created:
            setup.header01 = store_name
            setup.save()
            self.stdout.write(f"Updated store: {store_name}")
        else:
            self.stdout.write(f"Created store: {store_name}")

        self.stdout.write(self.style.SUCCESS("Done. Store name will appear in POS header."))
