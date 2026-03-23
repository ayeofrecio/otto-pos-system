from datetime import datetime

from django.db import models

# Create your models here.
class TerminalSetup(models.Model):

    store_id = models.CharField(max_length=3)
    terminal_id = models.CharField(max_length=3)

    vat = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    open_time = models.TimeField(default=datetime.time(9,0))
    cutoff_time = models.TimeField(default=datetime.time(4,0))

    class Meta:
        db_table = "terminal_setup"
        unique_together = [["store_id","terminal_id"]]

    def __str__(self):
        return f"{self.store_id}/{self.terminal_id}"
    

class TerminalReceiptHeader(models.Model):

    terminal = models.ForeignKey(
        TerminalSetup,
        on_delete=models.CASCADE,
        related_name="headers"
    )

    line_number = models.PositiveSmallIntegerField()
    header_text = models.CharField(max_length=40)

    class Meta:
        db_table = "terminal_receipt_headers"
        ordering = ["line_number"]


class TerminalReceiptFooter(models.Model):

    terminal = models.ForeignKey(
        TerminalSetup,
        on_delete=models.CASCADE,
        related_name="footers"
    )

    line_number = models.PositiveSmallIntegerField()
    footer_text = models.CharField(max_length=40)

    class Meta:
        db_table = "terminal_receipt_footers"
        ordering = ["line_number"]


class TerminalPort(models.Model):

    PORT_TYPES = [
        ("PRINTER","Printer"),
        ("DRAWER","Cash Drawer"),
        ("DISPLAY","Pole Display"),
    ]

    terminal = models.ForeignKey(
        TerminalSetup,
        on_delete=models.CASCADE,
        related_name="ports"
    )

    port_type = models.CharField(max_length=10, choices=PORT_TYPES)
    port_name = models.CharField(max_length=10)

    class Meta:
        db_table = "terminal_ports"


class TerminalDisplayCode(models.Model):

    terminal = models.ForeignKey(
        TerminalSetup,
        on_delete=models.CASCADE,
        related_name="display_codes"
    )

    code_group = models.CharField(max_length=2)
    code_value = models.CharField(max_length=5, blank=True)
    code_length = models.CharField(max_length=2, blank=True)

    class Meta:
        db_table = "terminal_display_codes"


