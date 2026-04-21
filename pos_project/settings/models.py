from datetime import datetime, time

from django.db import models

# Create your models here.
class TerminalSetup(models.Model):

    store_id = models.CharField(max_length=3)
    terminal_id = models.CharField(max_length=3)

    vat = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    open_time = models.TimeField(default=time(9, 0))
    cutoff_time = models.TimeField(default=time(4, 0))

    class Meta:
        db_table = "terminal_setup"
        unique_together = [["store_id","terminal_id"]]

    def __str__(self):
        return f"{self.store_id}/{self.terminal_id}"

