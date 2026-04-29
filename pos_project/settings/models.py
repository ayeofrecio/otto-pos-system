from datetime import datetime, time

from django.db import models

# ---------------------------------------------------------------------------
# For Checking Terminal Setup and Configuration
# ---------------------------------------------------------------------------
class TerminalConfiguration(models.Model):

    CONNECTION_TYPES = [
        ("SERIAL","Serial"),
        ("USB","USB"),
        ("NETWORK","Network"),
    ]
    
    store_id = models.CharField(max_length=3)
    terminal_id = models.CharField(max_length=3)
    branch_name = models.CharField(max_length=20, blank=True)
    vat = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    print_in = models.CharField(max_length=10, choices=CONNECTION_TYPES, default="SERIAL")
    open_time = models.TimeField(default=datetime.time(9,0))
    cutoff_time = models.TimeField(default=datetime.time(4,0))

    class Meta:
        db_table = "terminal_configurations"
        unique_together = [["store_id","terminal_id"]]

    def __str__(self):
        return f"{self.store_id}/{self.terminal_id}"

class TerminalReceiptHeader(models.Model):

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="headers"
    )

    line_number = models.PositiveSmallIntegerField()
    header_text = models.CharField(max_length=40)
    is_capitalized = models.BooleanField(default=False)

    class Meta:
        db_table = "terminal_receipt_headers"
        ordering = ["line_number"]

class TerminalReceiptFooter(models.Model):

    FOOTER_TYPE_CHOICES = [
        ("customer", "Customer Copy"),
        ("record", "Record Copy"),
        ("both", "Both Copies"),
    ]

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="footers"
    )

    footer_type = models.CharField(
        max_length=10,
        choices=FOOTER_TYPE_CHOICES,
        default="customer"
    )

    line_number = models.PositiveSmallIntegerField()
    footer_text = models.CharField(max_length=40)
    is_centered = models.BooleanField(default=False)
    is_left_align = models.BooleanField(default=False)

    class Meta:
        db_table = "terminal_receipt_footers"
        ordering = ["line_number"]


class TerminalPort(models.Model):

    PORT_TYPES = [
        ("PRINTER","Printer"),
        ("DRAWER","Cash Drawer"),
        ("DISPLAY","Pole Display"),
    ]

    CONNECTION_TYPES = [
        ("SERIAL","Serial"),
        ("USB","USB"),
        ("NETWORK","Network"),
        ("WINDOWS","Windows"),
    ]

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="ports"
    )

    port_type = models.CharField(max_length=10, choices=PORT_TYPES)
    connection_type = models.CharField(max_length=10, choices=CONNECTION_TYPES)
    
    # General field (existing)
    port_name = models.CharField(max_length=50, blank=True, null=True)

    # New fields for multi-connection support
    baudrate = models.IntegerField(blank=True, null=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)
    port_no = models.IntegerField(blank=True, null=True)
    printer_name = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "terminal_ports"


class TerminalDisplayCode(models.Model):

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="display_codes"
    )

    code_group = models.CharField(max_length=2)
    code_value = models.CharField(max_length=5, blank=True)
    code_length = models.CharField(max_length=2, blank=True)

    class Meta:
        db_table = "terminal_display_codes"


class TerminalFileDirectories(models.Model):

    terminal = models.ForeignKey(
        TerminalConfiguration,
        on_delete=models.CASCADE,
        related_name="file_directories"
    )

    directory_path = models.CharField(max_length=255)
    items_csv_path = models.CharField(max_length=255, blank=True)
    itemdtl_csv_path = models.CharField(max_length=255, blank=True)
    itemscosts_csv_path = models.CharField(max_length=255, blank=True)


    class Meta:
        db_table = "terminal_file_directories"  