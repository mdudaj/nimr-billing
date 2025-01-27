# Generated by Django 4.2.9 on 2025-01-27 20:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0028_alter_cancelledbill_bill'),
    ]

    operations = [
        migrations.AlterField(
            model_name='revenuesourceitem',
            name='currency',
            field=models.CharField(choices=[('TZS', 'Tanzanian Shilling'), ('USD', 'United States Dollar')], default='TZS', max_length=3, verbose_name='Currency Code'),
        ),
    ]
