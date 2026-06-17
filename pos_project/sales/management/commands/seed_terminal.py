import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from sales.models import (
    TerminalConfiguration,
    TerminalReceiptHeader,
    TerminalReceiptFooter,
    TerminalPort,
    TerminalDisplayCode
)

class Command(BaseCommand):
    help = "Seeds the database with default Terminal Configurations and related sub-settings"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting Terminal data seeding..."))

        # 1. Create the Main Terminal Configuration
        # Uses get_or_create to prevent duplicate entries if run multiple times
        terminal, created = TerminalConfiguration.objects.get_or_create(
            store_id="001",
            terminal_id="001",
            defaults={
                "store_name": "OTTO GENERAL MERCHANDISE",
                "branch_name": "Mambugan",
                "vat": Decimal("12.0000"), # Standard 12% VAT
                "print_in": "SERIAL",   
                "open_time": datetime.time(8, 0),
                "cutoff_time": datetime.time(4, 0),
            }
        )

        if created:
            self.stdout.write(f"Created fresh Terminal Configuration: {terminal}")
        else:
            self.stdout.write(f"Terminal Configuration {terminal} already exists. Syncing relational data...")

        # 2. Hardcoded Receipt Headers
        headers_data = [
            {"line_number": 1, "header_text": "OTTO GENERAL MERCHANDISE", "is_capitalized": True},
            {"line_number": 2, "header_text": "MANUEL P. SAMSON", "is_capitalized": False},
            {"line_number": 3, "header_text": "VAT Registered TIN 100-152-703-064", "is_capitalized": False},
            {"line_number": 4, "header_text": "MIN: 15110713481231907", "is_capitalized": True},
            {"line_number": 5, "header_text": "SERIAL NO.: FLEG030288", "is_capitalized": True},
            {"line_number": 6, "header_text": "NE PACIFIC MALL MAHARLIKA HI-WAY", "is_capitalized": True},
            {"line_number": 7, "header_text": "CABANATUAN CITY", "is_capitalized": True},
        ]
        
        for hd in headers_data:
            TerminalReceiptHeader.objects.get_or_create(
                terminal=terminal,
                line_number=hd["line_number"],
                defaults={"header_text": hd["header_text"], "is_capitalized": hd["is_capitalized"]}
            )

        # 3. Hardcoded Receipt Footers
        footers_data = [
            {"line_number": 1, "footer_text": "CUSTOMER NAME : _____________________", "footer_type": "both", "is_centered": True},
            {"line_number": 2, "footer_text": "ADRESS : ______________________", "footer_type": "customer", "is_centered": True},
            {"line_number": 3, "footer_text": "TIN : ____________________", "footer_type": "record", "is_left_align": True, "is_centered": True},
            {"line_number": 4, "footer_text": "BUSS : ____________________", "footer_type": "record", "is_left_align": True, "is_centered": True},
            {"line_number": 5, "footer_text": " ", "footer_type": "record", "is_left_align": True, "is_centered": True},
            {"line_number": 6, "footer_text": "Manuel P. Samson / OTTOPOS VER 1", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 7, "footer_text": "232 Sumulong HWY Mambugan Antipolo City", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 8, "footer_text": "TIN : 100-152-703-000", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 9, "footer_text": "AN : 045-100-152-703-000202-7382", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 10, "footer_text": "Permit No. : FP112015-23B-0062140-00064 ", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 11, "footer_text": "Date of Issuance : 11/18/2015", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 12, "footer_text": "Effectivity Date", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 13, "footer_text": " ", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 14, "footer_text": "FOR RETURN & EXCHANGE, item must be", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 15, "footer_text": "unused, in good condition & contains", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 16, "footer_text": "all original packaging. It must be", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 17, "footer_text": "returned with RECEIPT within 7 days", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 18, "footer_text": "from purchased date.", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 19, "footer_text": " ", "footer_type": "record", "is_left_align": False, "is_centered": True},
            {"line_number": 20, "footer_text": "www.ottoshoes.com.ph", "footer_type": "record", "is_left_align": False, "is_centered": True},
        ]

        for fd in footers_data:
            TerminalReceiptFooter.objects.get_or_create(
                terminal=terminal,
                line_number=fd["line_number"],
                defaults={
                    "footer_text": fd["footer_text"],
                    "footer_type": fd["footer_type"],
                    "is_centered": fd["is_centered"],
                    "is_left_align": fd.get("is_left_align", False)
                }
            )

        # 4. Hardcoded Hardware Ports
        ports_data = [
            {
                "port_type": "PRINTER",
                "connection_type": "SERIAL",
                "printer_name": "EPSON",
                "port_name": "COM1",
                "baudrate": 9600
            },
            {
                "port_type": "PRINTER",
                "connection_type": "WINDOWS",
                "port_name": "EpsonGeneric",
            },
            # {
            #     "port_type": "DISPLAY",
            #     "connection_type": "NETWORK",
            #     "ip_address": "192.168.1.200",
            #     "port_no": 9100
            # }
        ]

        for pd in ports_data:
            TerminalPort.objects.get_or_create(
                terminal=terminal,
                port_type=pd["port_type"],
                defaults={
                    "connection_type": pd["connection_type"],
                    "port_name": pd.get("port_name"),
                    "baudrate": pd.get("baudrate"),
                    "ip_address": pd.get("ip_address"),
                    "port_no": pd.get("port_no"),
                    "printer_name": pd.get("printer_name"),
                }
            )

        # 5. Hardcoded Display Pole / Customer Display Codes
        display_codes_data = [
            {"code_group": "01", "code_value": "CLR", "code_length": "02"}, # Clear screen
            {"code_group": "02", "code_value": "WRE", "code_length": "05"}, # Write string
            {"code_group": "03", "code_value": "RST", "code_length": "02"}, # Reset hardware
        ]

        for cd in display_codes_data:
            TerminalDisplayCode.objects.get_or_create(
                terminal=terminal,
                code_group=cd["code_group"],
                defaults={"code_value": cd["code_value"], "code_length": cd["code_length"]}
            )

        self.stdout.write(self.style.SUCCESS("🎉 Terminal components successfully seeded!"))