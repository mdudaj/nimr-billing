# Generated by Django 4.2.9 on 2024-08-07 07:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_rename_pay_channel_paymentreconciliation_usd_pay_chnl_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='bill',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='billing.bill', verbose_name='Bill'),
        ),
    ]
