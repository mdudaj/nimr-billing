# Generated by Django 4.2.9 on 2024-09-18 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0013_alter_cancelledbill_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bill',
            name='gen_date',
            field=models.DateTimeField(auto_now=True, help_text='The date when the bill was generated', verbose_name='Bill Issue Date'),
        ),
    ]
