# Generated by Django 4.2.9 on 2024-03-26 09:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_alter_bill_options_rename_date_bill_gen_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='rev_src',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='billing.revenuesource', verbose_name='Revenue Source'),
            preserve_default=False,
        ),
    ]
