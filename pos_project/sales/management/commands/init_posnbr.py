"""
Initialize or update POSNBR transaction number safely.

Usage:
  python manage.py init_posnbr --start 00012345
  python manage.py init_posnbr --start 12345 --force

Behavior:
- If POSNBR has no row yet: creates one with --start.
- If POSNBR already has a row: does not overwrite unless --force is set.
"""

from django.core.management.base import BaseCommand, CommandError

from sales.models import POSTransNumber


class Command(BaseCommand):
    help = "Initialize POSNBR.transaction_no with a chosen starting number"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            required=True,
            help="Starting transaction number (e.g. 1 or 00000001)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing POSNBR transaction_no",
        )

    def _normalize(self, raw):
        text = str(raw).strip()
        if not text:
            raise CommandError("--start is required")
        if not text.isdigit():
            raise CommandError("--start must be numeric (e.g. 1 or 00000001)")

        number = int(text)
        if number < 0:
            raise CommandError("--start cannot be negative")
        if number > 99999999:
            raise CommandError("--start must be <= 99999999")

        return str(number).zfill(8)

    def handle(self, *args, **options):
        start_no = self._normalize(options["start"])
        force = options["force"]

        row = POSTransNumber.objects.order_by("id").first()

        if row is None:
            POSTransNumber.objects.create(transaction_no=start_no)
            self.stdout.write(self.style.SUCCESS(f"Created POSNBR with transaction_no={start_no}"))
            return

        current = row.transaction_no or ""
        if not force:
            self.stdout.write(
                self.style.WARNING(
                    "POSNBR already exists with transaction_no="
                    f"{current}. No changes made. Use --force to overwrite."
                )
            )
            return

        row.transaction_no = start_no
        row.save(update_fields=["transaction_no"])
        self.stdout.write(self.style.SUCCESS(f"Updated POSNBR transaction_no: {current} -> {start_no}"))
