# Generated by Django 4.2.9 on 2024-10-09 11:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0018_alter_payment_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentreconciliation',
            name='sp_code',
            field=models.CharField(blank=True, max_length=10, null=True, verbose_name='Service Provider Code'),
        ),
    ]