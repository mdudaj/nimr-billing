# Generated by Django 4.2.9 on 2024-08-01 08:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Bill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bill_id', models.CharField(help_text='Unique identification of the Bill in Service Provider Billing System', max_length=100, unique=True, verbose_name='Bill ID')),
                ('grp_bill_id', models.CharField(help_text='Unique identification of the Group Bill in Service Provider Billing System', max_length=100, unique=True, verbose_name='Group Bill ID')),
                ('type', models.PositiveSmallIntegerField(choices=[(1, 'Normal Bill Control Number'), (2, 'Combined Bill Control Number')], default=1, verbose_name='Bill Type')),
                ('pay_type', models.PositiveSmallIntegerField(choices=[(1, 'Pay All Bill Control Numbers At Once'), (2, 'Pay any Bill Control Number')], default=2, verbose_name='Payment Type')),
                ('description', models.CharField(blank=True, max_length=500, null=True, verbose_name='Bill Description')),
                ('amt', models.DecimalField(blank=True, decimal_places=2, max_digits=32, null=True, verbose_name='Bill Amount')),
                ('eqv_amt', models.DecimalField(blank=True, decimal_places=2, max_digits=32, null=True, verbose_name='Bill Equivalent Amount')),
                ('min_amt', models.DecimalField(blank=True, decimal_places=2, help_text='The minimum amount payable value', max_digits=32, null=True, verbose_name='Minimum Payment Amount')),
                ('max_amt', models.DecimalField(blank=True, decimal_places=2, help_text='The maximum limitation value for a transaction', max_digits=32, null=True, verbose_name='Payment Limitation Amount')),
                ('pay_lim_type', models.PositiveSmallIntegerField(choices=[(1, 'Normal Payment (No limitation)'), (2, 'All Commercial Bank Payment Limitation'), (3, 'Central Bank Limitation'), (4, 'Central Bank and Specific Commercial Bank Limitation'), (5, 'Specific Commercial Bank Limitation')], default=1, verbose_name='Bill Payment Limitation Type')),
                ('currency', models.CharField(choices=[('TZS', 'Tanzanian Shilling'), ('USD', 'United States Dollar')], default='TZS', max_length=3, verbose_name='Currency Code')),
                ('exch_rate', models.DecimalField(decimal_places=2, default=1.0, max_digits=32)),
                ('pay_opt', models.PositiveSmallIntegerField(choices=[(1, 'FULL Bill'), (2, 'PARTIAL Bill'), (3, 'EXACT Bill'), (4, 'INFINITY payment option'), (5, 'LIMITED payment option')], default=3)),
                ('pay_plan', models.PositiveSmallIntegerField(choices=[(1, 'POST-PAID'), (2, 'PRE-PAID')], default=1, verbose_name='Payment Plan')),
                ('gen_date', models.DateTimeField(auto_now_add=True, help_text='The date when the bill was generated', verbose_name='Bill Issue Date')),
                ('expr_date', models.DateTimeField(help_text='The date when the bill will expire', verbose_name='Bill Expiry Date')),
                ('gen_by', models.CharField(blank=True, max_length=30, null=True, verbose_name='Bill Generated By')),
                ('appr_by', models.CharField(blank=True, max_length=30, null=True, verbose_name='Bill Approved By')),
                ('cntr_num', models.BigIntegerField(blank=True, null=True, unique=True, verbose_name='Bill Control Number')),
            ],
            options={
                'verbose_name': 'Bill',
                'verbose_name_plural': 'Bills',
                'ordering': ['gen_date'],
            },
        ),
        migrations.CreateModel(
            name='BillingDepartment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Collection Center Name')),
                ('description', models.CharField(blank=True, help_text='Billing Dept. Description', max_length=255, null=True, verbose_name='Description')),
                ('code', models.CharField(blank=True, max_length=20, null=True, unique=True, verbose_name='Collection Center Code')),
                ('account_num', models.CharField(max_length=50, verbose_name='Credit Collection Account Number')),
            ],
            options={
                'verbose_name': 'Billing Department',
                'verbose_name_plural': 'Billing Departments',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('first_name', models.CharField(max_length=66, verbose_name='First Name')),
                ('middle_name', models.CharField(blank=True, max_length=66, null=True, verbose_name='Middle Name')),
                ('last_name', models.CharField(max_length=66, verbose_name='Last Name')),
                ('tin', models.CharField(blank=True, default='000000000', help_text='Customer Tax Identification Number', max_length=20, null=True, verbose_name='Customer TIN')),
                ('id_num', models.CharField(default='19000715-00001-00001-01', help_text='Customer Identification Reference', max_length=50, verbose_name='Customer ID')),
                ('id_type', models.CharField(choices=[('1', 'National Identification Number'), ('2', "Driver's License"), ('3', "TaxPayer's Identification"), ('4', 'Wallet Pay Number')], default='1', help_text='Customer Identification Reference Type', max_length=50, verbose_name='Customer ID Type')),
                ('account_num', models.CharField(blank=True, default='000000000000', help_text='Customer Account Number', max_length=50, null=True, verbose_name='Customer Account')),
                ('cell_num', models.CharField(blank=True, help_text='Customer Mobile/Cell Number should have twelve digits including country code e.g. 255XXXXXXXXX', max_length=12, null=True, verbose_name='Customer Cell Number')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, unique=True, verbose_name='Customer Email')),
            ],
            options={
                'verbose_name': 'Customer',
                'verbose_name_plural': 'Customers',
                'ordering': ['last_name', 'first_name'],
            },
        ),
        migrations.CreateModel(
            name='RevenueSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255, verbose_name='Revenue Source Name')),
                ('gfs_code', models.CharField(max_length=20, verbose_name='GFS Code')),
                ('category', models.CharField(max_length=255, verbose_name='Revenue Category')),
                ('sub_category', models.CharField(max_length=255, verbose_name='Revenue Sub-Category')),
            ],
            options={
                'verbose_name': 'Revenue Source',
                'verbose_name_plural': 'Revenue Sources',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ServiceProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200, verbose_name='Service Provider Name')),
                ('code', models.CharField(max_length=10, unique=True, verbose_name='Service Provider Code')),
                ('grp_code', models.CharField(max_length=10, unique=True, verbose_name='Service Provider Group Code')),
                ('sys_code', models.CharField(max_length=10)),
            ],
            options={
                'verbose_name': 'Service Provider',
                'verbose_name_plural': 'Service Providers',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SystemInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='Integrating System Code')),
                ('name', models.CharField(max_length=200, verbose_name='Intergating System Name')),
                ('cntrnum_response_callback', models.URLField(help_text='URL to receive bill control number response from the billing system', verbose_name='Bill Control Number Response Callback URL')),
                ('pay_notification_callback', models.URLField(help_text='URL to receive payment notifications from the billing system', verbose_name='Notification Callback URL')),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'System Information',
                'verbose_name_plural': 'System Information',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RevenueSourceItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('description', models.CharField(help_text='Item Description', max_length=255, verbose_name='Description')),
                ('amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Item Amount')),
                ('currency', models.CharField(choices=[('TZS', 'Tanzanian Shilling'), ('USD', 'United States Dollar')], default='TZS', max_length=3, verbose_name='Currency Code')),
                ('rev_src', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.revenuesource', verbose_name='Revenue Source')),
            ],
            options={
                'verbose_name': 'Revenue Source Item',
                'verbose_name_plural': 'Revenue Source Items',
                'ordering': ['rev_src'],
            },
        ),
        migrations.CreateModel(
            name='PaymentReconciliation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cust_cntr_num', models.BigIntegerField(verbose_name='Customer Control Number')),
                ('psp_code', models.CharField(max_length=10, verbose_name='Payment Service Provider Code')),
                ('psp_name', models.CharField(max_length=200, verbose_name='Payment Service Provider Name')),
                ('trx_id', models.CharField(max_length=100, verbose_name='Payment Service Provider Transaction ID')),
                ('payref_id', models.CharField(max_length=100, verbose_name='Payment receipt issued by GEPG')),
                ('bill_amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Bill Amount')),
                ('paid_amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Amount Paid')),
                ('currency', models.CharField(max_length=3, verbose_name='Paid amount currency')),
                ('coll_acc_num', models.CharField(max_length=50, verbose_name='Credited Collection Account Number')),
                ('trx_date', models.DateTimeField(verbose_name='Transaction Date')),
                ('pay_channel', models.CharField(max_length=50, verbose_name='Payment provider payment channel used to pay the bill')),
                ('trdpty_trx_id', models.CharField(help_text='Third Party Receipt such as Issuing Bank authorization Identification, MNO Receipt, Aggregator Receipt etc.', max_length=50, verbose_name='Third Party Transaction ID')),
                ('pyr_name', models.CharField(blank=True, help_text='Payer Name as received from payment service provider', max_length=200, null=True, verbose_name='Payer Name')),
                ('pyr_cell_num', models.CharField(blank=True, help_text='Payer Mobile/Cell Number should have twelve digits including country code e.g. 255XXXXXXXXX', max_length=12, null=True, verbose_name='Payer Cell Number')),
                ('pyr_email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Payer Email')),
                ('pay_status', models.CharField(help_text='Reconciliation Status Description', max_length=500, verbose_name='Payment Reconciliation Status')),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.bill', verbose_name='Bill')),
            ],
            options={
                'verbose_name': 'Payment Reconciliation',
                'verbose_name_plural': 'Payment Reconciliations',
                'ordering': ['trx_date'],
            },
        ),
        migrations.CreateModel(
            name='PaymentGatewayLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('req_id', models.CharField(max_length=100, unique=True, verbose_name='Request ID')),
                ('req_type', models.CharField(choices=[('1', 'Bill Control Number Request'), ('2', 'Bill Control Number Reuse Request'), ('3', 'Bill Control Number Change Request'), ('4', 'Bill Control Number Cancellation Request'), ('5', 'BILL Payment Notification Request'), ('6', 'BILL Payment Reconciliation Request')], max_length=1, verbose_name='Request Type')),
                ('status', models.CharField(max_length=50, verbose_name='Request Status')),
                ('status_desc', models.CharField(max_length=255, verbose_name='Request Status Description')),
                ('req_data', models.JSONField(blank=True, null=True, verbose_name='Request Data')),
                ('req_ack', models.JSONField(blank=True, null=True, verbose_name='Request Acknowledgement')),
                ('res_data', models.JSONField(blank=True, null=True, verbose_name='Response Data')),
                ('res_ack', models.JSONField(blank=True, null=True, verbose_name='Response Acknowledgement')),
                ('bill', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='billing.bill', verbose_name='Bill')),
                ('sys_info', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='billing.systeminfo', verbose_name='Integrating System Information')),
            ],
            options={
                'verbose_name': 'Payment Gateway Log',
                'verbose_name_plural': 'Payment Gateway Logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cust_cntr_num', models.BigIntegerField(verbose_name='Customer Control Number')),
                ('psp_code', models.CharField(max_length=10, verbose_name='Payment Service Provider Code')),
                ('psp_name', models.CharField(max_length=200, verbose_name='Payment Service Provider Name')),
                ('trx_id', models.CharField(max_length=100, verbose_name='Payment Service Provider Transaction ID')),
                ('payref_id', models.CharField(max_length=100, verbose_name='Payment receipt issued by GEPG')),
                ('bill_amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Bill Amount')),
                ('paid_amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Amount Paid')),
                ('currency', models.CharField(max_length=3, verbose_name='Paid amount currency')),
                ('coll_acc_num', models.CharField(max_length=50, verbose_name='Credited Collection Account Number')),
                ('trx_date', models.DateTimeField(verbose_name='Transaction Date')),
                ('pay_channel', models.CharField(max_length=50, verbose_name='Payment provider payment channel used to pay the bill')),
                ('trdpty_trx_id', models.CharField(help_text='Third Party Receipt such as Issuing Bank authorization Identification, MNO Receipt, Aggregator Receipt etc.', max_length=50, verbose_name='Third Party Transaction ID')),
                ('pyr_name', models.CharField(blank=True, help_text='Payer Name as received from payment service provider', max_length=200, null=True, verbose_name='Payer Name')),
                ('pyr_cell_num', models.CharField(blank=True, help_text='Payer Mobile/Cell Number should have twelve digits including country code e.g. 255XXXXXXXXX', max_length=12, null=True, verbose_name='Payer Cell Number')),
                ('pyr_email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Payer Email')),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.bill', verbose_name='Bill')),
            ],
            options={
                'verbose_name': 'Payment',
                'verbose_name_plural': 'Payments',
                'ordering': ['trx_date'],
            },
        ),
        migrations.CreateModel(
            name='BillItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ref_on_pay', models.CharField(default='N', help_text='The value should be “N”', max_length=1, verbose_name='Use Item Reference on Payment')),
                ('description', models.CharField(help_text='Item Description', max_length=255, verbose_name='Description')),
                ('qty', models.PositiveIntegerField(default=1, verbose_name='Bill Item Quantity')),
                ('amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Bill Item Amount')),
                ('eqv_amt', models.DecimalField(decimal_places=2, max_digits=32, verbose_name='Bill Item Equivalent Amount')),
                ('misc_amt', models.DecimalField(decimal_places=2, default=0.0, max_digits=32, verbose_name='Bill Item Miscellaneous Amount')),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.bill', verbose_name='Bill')),
                ('dept', models.ForeignKey(help_text='The billing department that issued the bill', on_delete=django.db.models.deletion.CASCADE, to='billing.billingdepartment', verbose_name='Billing Department')),
                ('rev_src_itm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.revenuesourceitem', verbose_name='Revenue Source')),
            ],
            options={
                'verbose_name': 'Bill Item',
                'verbose_name_plural': 'Bill Items',
                'ordering': ['bill'],
            },
        ),
        migrations.AddField(
            model_name='billingdepartment',
            name='service_provider',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.serviceprovider', verbose_name='Service Provider'),
        ),
        migrations.AddField(
            model_name='bill',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.customer', verbose_name='Customer'),
        ),
        migrations.AddField(
            model_name='bill',
            name='dept',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.billingdepartment', verbose_name='Billing Department'),
        ),
        migrations.AddField(
            model_name='bill',
            name='sys_info',
            field=models.ForeignKey(blank=True, help_text='The integrating system that generated the bill', null=True, on_delete=django.db.models.deletion.SET_NULL, to='billing.systeminfo', verbose_name='Integrating System Information'),
        ),
    ]
