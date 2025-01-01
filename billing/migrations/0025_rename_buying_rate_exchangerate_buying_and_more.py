# Generated by Django 4.2.9 on 2025-01-01 09:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0024_currency_alter_payment_trdpty_trx_id_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='exchangerate',
            old_name='buying_rate',
            new_name='buying',
        ),
        migrations.RenameField(
            model_name='exchangerate',
            old_name='selling_rate',
            new_name='selling',
        ),
        migrations.CreateModel(
            name='RevenueSourceItemPriceHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Item Amount')),
                ('effective_date', models.DateTimeField(verbose_name='Effective Date')),
                ('rev_src_itm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_history', to='billing.revenuesourceitem', verbose_name='Revenue Source Item')),
            ],
            options={
                'verbose_name': 'Revenue Source Item Price History',
                'verbose_name_plural': 'Revenue Source Item Price Histories',
                'ordering': ['-effective_date'],
            },
        ),
    ]
