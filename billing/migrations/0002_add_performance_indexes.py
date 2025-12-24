# Generated manually for performance optimization

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),  # Replace with your latest migration
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_paymentgatewaylog_bill_type ON billing_paymentgatewaylog(bill_id, req_type);",
            reverse_sql="DROP INDEX IF EXISTS idx_paymentgatewaylog_bill_type;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_paymentgatewaylog_created_at ON billing_paymentgatewaylog(created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_paymentgatewaylog_created_at;"
        ),
    ]
