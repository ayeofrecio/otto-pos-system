# Generated manually for POS cashier

from django.db import migrations


def seed_pos_trans_counter(apps, schema_editor):
    POSTransCounter = apps.get_model("sales", "POSTransCounter")
    if not POSTransCounter.objects.exists():
        POSTransCounter.objects.create(transaction_no="00000001")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial_clarion_models"),
    ]

    operations = [
        migrations.RunPython(seed_pos_trans_counter, noop),
    ]
