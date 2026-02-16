from django.db import migrations, models
import django.db.models.deletion


def seed_department_accounts(apps, schema_editor):
    BillingDepartment = apps.get_model("billing", "BillingDepartment")
    BillingDepartmentAccount = apps.get_model("billing", "BillingDepartmentAccount")

    for dept in BillingDepartment.objects.all().iterator():
        if not getattr(dept, "account_num", None):
            continue
        if not getattr(dept, "bank", None):
            continue

        BillingDepartmentAccount.objects.get_or_create(
            billing_department=dept,
            bank=dept.bank,
            account_currency_id=dept.account_currency_id,
            account_num=dept.account_num,
            defaults={"bank_swift_code": dept.bank_swift_code},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0031_alter_bill_currency_billingemaildelivery_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingDepartmentAccount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bank",
                    models.CharField(
                        choices=[("CRDB", "CRDB Bank PLC"), ("NBC", "National Bank of Commerce"), ("NMB", "NMB Bank PLC")],
                        max_length=10,
                        verbose_name="Bank Name",
                    ),
                ),
                (
                    "bank_swift_code",
                    models.CharField(max_length=20, verbose_name="Bank Swift Code"),
                ),
                (
                    "account_num",
                    models.CharField(
                        max_length=50,
                        verbose_name="Credit Collection Account Number",
                    ),
                ),
                (
                    "account_currency",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="billing.currency",
                        verbose_name="Account Currency",
                    ),
                ),
                (
                    "billing_department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounts",
                        to="billing.billingdepartment",
                        verbose_name="Collection Center",
                    ),
                ),
            ],
            options={
                "verbose_name": "Billing Department Account",
                "verbose_name_plural": "Billing Department Accounts",
                "ordering": [
                    "billing_department",
                    "bank",
                    "account_currency_id",
                    "account_num",
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="billingdepartmentaccount",
            constraint=models.UniqueConstraint(
                fields=("billing_department", "bank", "account_currency", "account_num"),
                name="uniq_dept_bank_currency_account",
            ),
        ),
        migrations.RunPython(seed_department_accounts, migrations.RunPython.noop),
    ]

