"""
Seed POS function keycodes into the functions table.
Source: FUNCTION.DBF (Clipper/Clarion original data)
Run: python manage.py seed_functions
"""

from django.core.management.base import BaseCommand

from sales.models import POSFunction


# Original keycode values from FUNCTION.DBF
# Stored as Clipper chr() equivalents (raw single-byte characters)
FUNCTIONS_DATA = [
    ("pIViewKey",  "Item Lookup",                   "\x03"),
    ("pIDiscKey",  "Item Discount",                 "\xff"),
    ("pSTDiscKey", "SubTotal Discount",             "\xfe"),
    ("pPrOverKey", "Price Override",                "\xfd"),
    ("pIRetKey",   "Item Return",                   "\xfc"),
    ("pIVoidKey",  "Line Item Void",                "\xfb"),
    ("pIVoidAKey", "Void All Item",                 "\xfa"),
    ("pVoidTrKey", "Void Previous Transaction",     "\xf9"),
    ("pISusRtKey", "Transaction Suspend/Retreived", "\xf8"),
    ("pSubTotKey", "SubTotal",                      "\xf7"),
    ("pPaymntKey", "Payment",                       "\xd8"),
    ("pIQtyKey",   "Quantity",                      "\x06"),
    ("pTSRepKey",  "X-Reading/Terminal Sales",      "X"),
    ("pJRepKey",   "Journal Report",                "J"),
    ("pSOffKey",   "Sign Off/Log Off User",         "\x07"),
    ("pMenuKey",   "Menu Key",                      "\x1c"),
    ("pZReadKey",  "Z-Reading/End Of Day",          "Z"),
    ("pStatKey",   "Sales Status",                  "S"),
    ("pAPlusKey",  "Add On Amount/Percent",         "A"),
    ("pODeptKey",  "Open Department",               "\xe9"),
    ("pSmanKey",   "Reprint Transactions",          "Q"),
    ("pCWithDKey", "Cash Withdrawal",               "W"),
    ("pViewTxt",   "View Uploaded Textfile",        "V"),
    ("pResendTxt", "Resend Text file",              "R"),
]


class Command(BaseCommand):
    help = "Seed POS function keycodes from original FUNCTION.DBF data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset all keycodes back to original DBF values even if they already exist",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for code, desc, key_code in FUNCTIONS_DATA:
            obj, created = POSFunction.objects.get_or_create(
                code=code,
                defaults={
                    "desc":     desc,
                    "key_code": key_code,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(f"  Created : {code} ({desc})")

            elif reset:
                obj.desc     = desc
                obj.key_code = key_code
                obj.save()
                updated_count += 1
                self.stdout.write(f"  Updated : {code} ({desc})")

            else:
                skipped_count += 1
                self.stdout.write(f"  Skipped : {code} — already exists (use --reset to overwrite)")

        self.stdout.write("")
        self.stdout.write(f"  Created : {created_count}")
        self.stdout.write(f"  Updated : {updated_count}")
        self.stdout.write(f"  Skipped : {skipped_count}")
        self.stdout.write(self.style.SUCCESS("Done. POS function keycodes are ready."))