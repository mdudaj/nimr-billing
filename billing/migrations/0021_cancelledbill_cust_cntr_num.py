# Generated by Django 4.2.9 on 2024-10-10 13:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0020_alter_bill_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='cancelledbill',
            name='cust_cntr_num',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Cancelled Customer Control Number'),
        ),
    ]
