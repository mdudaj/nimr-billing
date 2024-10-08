# Generated by Django 4.2.9 on 2024-09-18 07:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('billing', '0011_alter_bill_pay_lim_type_alter_bill_pay_plan'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentgatewaylog',
            name='req_type',
            field=models.CharField(choices=[('1', 'Bill Control Number Request'), ('2', 'Bill Control Number Reuse Request'), ('3', 'Bill Control Number Change Request'), ('4', 'Bill Control Number Cancellation Request'), ('5', 'BILL Payment Notification Request'), ('6', 'BILL Payment Reconciliation Request'), ('7', 'BILL Cancellation Request')], max_length=1, verbose_name='Request Type'),
        ),
        migrations.CreateModel(
            name='CancelledBill',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bill', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='billing.bill', verbose_name='Bill')),
                ('reason', models.TextField(help_text='Reason for cancelling the bill', verbose_name='Cancellation Reason')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('CANCELLED', 'Cancelled'), ('FAILED', 'Failed')], default='PENDING', max_length=10, verbose_name='Cancellation Status')),
                ('appr_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancelled_bill_approved_by', to=settings.AUTH_USER_MODEL, verbose_name='Approved By')),
                ('gen_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancelled_bill_generated_by', to=settings.AUTH_USER_MODEL, verbose_name='Cancelled By')),
            ],
            options={
                'verbose_name': 'Cancelled Bill',
                'verbose_name_plural': 'Cancelled Bills',
                'ordering': ['-created_at'],
            },
        ),
    ]
