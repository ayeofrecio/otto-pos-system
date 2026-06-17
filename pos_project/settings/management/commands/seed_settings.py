"""
Seed default terminal setup values for POS.
Run: python manage.py seed_settings
"""

import datetime

from django.core.management.base import BaseCommand

from sales.models import (
    TerminalConfiguration,
    TerminalDisplayCode,
    TerminalPort,
    TerminalReceiptFooter,
    TerminalReceiptHeader,
#     TerminalSetup,
)
from sales.models import TerminalSetup


class Command(BaseCommand):
    help = "Seed sample terminal setup, receipt headers/footers, ports, and display codes."

    def handle(self, *args, **options):
        # ------------------------------------------------------------------
        # 1. TerminalSetup  (settings app — db_table: terminal_setup)
        # ------------------------------------------------------------------
        TerminalSetup.objects.get_or_create(
            store_id="001",
            terminal_id="001",
            defaults={
                "vat": 12.0000,
                "open_time": datetime.time(9, 0),
                "cutoff_time": datetime.time(4, 0),
            },
        )
        self.stdout.write("TerminalSetup 001/001 — done.")

        # ------------------------------------------------------------------
        # 2. TerminalConfiguration  (sales app — db_table: terminal_configurations)
        # ------------------------------------------------------------------
        terminal, created = TerminalConfiguration.objects.get_or_create(
            store_id="001",
            terminal_id="001",
            defaults={
                "branch_name": "Main Branch",
                "vat": 12.0000,
                "print_in": "SERIAL",
                "open_time": datetime.time(9, 0),
                "cutoff_time": datetime.time(4, 0),
            },
        )
        if created:
            self.stdout.write("Created TerminalConfiguration: 001/001")
        else:
            self.stdout.write("TerminalConfiguration 001/001 already exists — skipped.")

        # ------------------------------------------------------------------
        # 3. TerminalReceiptHeader
        # ------------------------------------------------------------------
        header_lines = [
            (1, "MY STORE NAME"),
            (2, "123 Main Street, City"),
            (3, "Tel: (02) 123-4567"),
            (4, "VAT Reg TIN: 000-000-000-000"),
            (5, "MIN: 00000000000"),
            (6, "S/N: 00000000000"),
        ]
        headers_created = 0
        for line_no, text in header_lines:
            _, c = TerminalReceiptHeader.objects.get_or_create(
                terminal=terminal,
                line_number=line_no,
                defaults={"header_text": text},
            )
            if c:
                headers_created += 1
        self.stdout.write(f"Created {headers_created} TerminalReceiptHeader row(s).")

        # ------------------------------------------------------------------
        # 4. TerminalReceiptFooter
        # ------------------------------------------------------------------
        footer_lines = [
            (1, "Thank you for shopping!"),
            (2, "Please keep this receipt."),
            (3, "No return / no exchange"),
            (4, "without official receipt."),
        ]
        footers_created = 0
        for line_no, text in footer_lines:
            _, c = TerminalReceiptFooter.objects.get_or_create(
                terminal=terminal,
                line_number=line_no,
                defaults={"footer_text": text},
            )
            if c:
                footers_created += 1
        self.stdout.write(f"Created {footers_created} TerminalReceiptFooter row(s).")

        # ------------------------------------------------------------------
        # 5. TerminalPort
        # ------------------------------------------------------------------
        ports_data = [
            ("PRINTER", "SERIAL", "COM1"),
            ("DRAWER",  "SERIAL", "COM2"),
            ("DISPLAY", "SERIAL", "COM3"),
        ]
        ports_created = 0
        for port_type, connection_type, port_name in ports_data:
            _, c = TerminalPort.objects.get_or_create(
                terminal=terminal,
                port_type=port_type,
                defaults={"connection_type": connection_type, "port_name": port_name},
            )
            if c:
                ports_created += 1
        self.stdout.write(f"Created {ports_created} TerminalPort row(s).")

        # ------------------------------------------------------------------
        # 6. TerminalDisplayCode
        # ------------------------------------------------------------------
        display_codes_data = [
            ("F1", "\x1b\x40",  "2"),   # Init / reset display
            ("L1", "\x1b\x51",  "2"),   # Line 1 prefix
            ("F2", "\x1b\x42",  "2"),   # Line 2 prefix
            ("L2", "\x0d",      "1"),   # Carriage return
        ]
        codes_created = 0
        for code_group, code_value, code_length in display_codes_data:
            _, c = TerminalDisplayCode.objects.get_or_create(
                terminal=terminal,
                code_group=code_group,
                defaults={
                    "code_value": code_value,
                    "code_length": code_length,
                },
            )
            if c:
                codes_created += 1
        self.stdout.write(f"Created {codes_created} TerminalDisplayCode row(s).")

        self.stdout.write(self.style.SUCCESS("Done. Terminal settings seeded successfully."))
