from django.db import migrations


def seed_currencies(apps, schema_editor):
    Currency = apps.get_model("billing", "Currency")

    Currency.objects.get_or_create(
        code="TZS",
        defaults={"name": "Tanzanian Shilling", "symbol": "TZS", "is_active": True},
    )
    Currency.objects.get_or_create(
        code="USD",
        defaults={"name": "United States Dollar", "symbol": "USD", "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0032_billingdepartmentaccount"),
    ]

    operations = [
        migrations.RunPython(seed_currencies, migrations.RunPython.noop),
    ]

