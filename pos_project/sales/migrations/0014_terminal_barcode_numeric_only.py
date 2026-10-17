from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0013_payment_card_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="terminalconfiguration",
            name="barcode_numeric_only",
            field=models.BooleanField(
                default=False,
                help_text="When on, the cashier barcode field accepts digits only.",
            ),
        ),
    ]
