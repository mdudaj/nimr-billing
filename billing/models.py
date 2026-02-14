import inflect
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# from rest_framework_api_key.models import AbstractAPIKey


User = get_user_model()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Currency(TimeStampedModel, models.Model):
    """Currency Information."""

    code = models.CharField(max_length=3, unique=True, verbose_name="Currency Code")
    name = models.CharField(max_length=50, verbose_name="Currency Name")
    symbol = models.CharField(
        max_length=5, verbose_name="Currency Symbol", blank=True, null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code}"

    def get_absolute_url(self):
        return reverse("billing:currency-detail", kwargs={"pk": self.pk})


class ExchangeRate(TimeStampedModel, models.Model):
    """Store Daily Currency Exchange Rate Information."""

    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        verbose_name="Currency",
        related_name="exchange_rates",
    )
    trx_date = models.DateField(verbose_name="Transaction Date")
    buying = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name="Buying Rate"
    )
    selling = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name="Selling Rate"
    )

    class Meta:
        verbose_name = "Exchange Rate"
        verbose_name_plural = "Exchange Rates"
        unique_together = ["currency", "trx_date"]
        ordering = ["-trx_date"]

    def __str__(self):
        return f"{self.currency.code} - {self.trx_date}"


class SystemInfo(TimeStampedModel, models.Model):
    """Integrating System's Information."""

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Integrating System Code",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Intergating System Name",
    )
    cntrnum_response_callback = models.URLField(
        verbose_name="Bill Control Number Response Callback URL",
        help_text="URL to receive bill control number response from the billing system",
    )
    pay_notification_callback = models.URLField(
        verbose_name="Notification Callback URL",
        help_text="URL to receive payment notifications from the billing system",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "System Information"
        verbose_name_plural = "System Information"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Customer(TimeStampedModel, models.Model):
    """Billing Customer."""

    CUST_ID_CHOICES = (
        ("1", _("National Identification Number")),
        ("2", _("Driver's License")),
        ("3", _("TaxPayer's Identification")),
        ("4", _("Wallet Pay Number")),
    )

    first_name = models.CharField(max_length=66, verbose_name=_("First Name"))
    middle_name = models.CharField(
        max_length=66, blank=True, null=True, verbose_name=_("Middle Name")
    )
    last_name = models.CharField(max_length=66, verbose_name=_("Last Name"))
    tin = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Customer TIN"),
        help_text="Customer Tax Identification Number",
        default="000000000",
    )
    id_num = models.CharField(
        max_length=50,
        verbose_name=_("Customer ID"),
        help_text="Customer Identification Reference",
        default="19000715-00001-00001-01",
    )
    id_type = models.CharField(
        max_length=50,
        choices=CUST_ID_CHOICES,
        verbose_name=_("Customer ID Type"),
        help_text="Customer Identification Reference Type",
        default="1",
    )
    account_num = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Customer Account"),
        help_text="Customer Account Number",
        default="000000000000",
    )
    cell_num = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        verbose_name=_("Customer Cell Number"),
        help_text=_(
            "Customer Mobile/Cell Number should have twelve digits including country code e.g. 255XXXXXXXXX"
        ),
    )
    email = models.EmailField(
        unique=True, blank=True, null=True, verbose_name=_("Customer Email")
    )

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ["last_name", "first_name"]

    def __str__(self):
        if self.middle_name is None:
            return f"{self.first_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    def get_name(self):
        if self.middle_name is None:
            return f"{self.first_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"


class ServiceProvider(TimeStampedModel, models.Model):
    """Billing Institution Service Provider."""

    name = models.CharField(max_length=200, verbose_name=_("Service Provider Name"))
    code = models.CharField(
        max_length=10, unique=True, verbose_name=_("Service Provider Code")
    )
    grp_code = models.CharField(
        max_length=10, unique=True, verbose_name=_("Service Provider Group Code")
    )
    sys_code = models.CharField(max_length=10)

    class Meta:
        verbose_name = _("Service Provider")
        verbose_name_plural = _("Service Providers")
        ordering = ["name"]

    def __str__(self):
        return self.name


class BillingDepartment(TimeStampedModel, models.Model):
    """Billing Department Collection Center Information."""

    Bank_Choices = (
        ("CRDB", _("CRDB Bank PLC")),
        ("NBC", _("National Bank of Commerce")),
        ("NMB", _("NMB Bank PLC")),
    )

    service_provider = models.ForeignKey(
        ServiceProvider, on_delete=models.CASCADE, verbose_name=_("Service Provider")
    )
    name = models.CharField(
        max_length=255, verbose_name=_("Collection Center Name"), unique=True
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text="Billing Dept. Description",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Collection Center Code"),
    )
    bank = models.CharField(
        max_length=10, choices=Bank_Choices, verbose_name=_("Bank Name")
    )
    bank_swift_code = models.CharField(max_length=20, verbose_name=_("Bank Swift Code"))
    account_num = models.CharField(
        max_length=50,
        verbose_name=_("Credit Collection Account Number"),
    )
    account_currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Account Currency"),
    )

    class Meta:
        verbose_name = _("Billing Department")
        verbose_name_plural = _("Billing Departments")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def get_dept(cls, name):
        try:
            dept = cls.objects.get(name=name)
            return dept
        except cls.DoesNotExist:
            return None


class BillingDepartmentAccount(TimeStampedModel, models.Model):
    """Collection account for a BillingDepartment (bank + currency specific)."""

    BANK_CHOICES = BillingDepartment.Bank_Choices

    billing_department = models.ForeignKey(
        BillingDepartment,
        on_delete=models.CASCADE,
        related_name="accounts",
        verbose_name=_("Collection Center"),
    )
    bank = models.CharField(
        max_length=10, choices=BANK_CHOICES, verbose_name=_("Bank Name")
    )
    bank_swift_code = models.CharField(max_length=20, verbose_name=_("Bank Swift Code"))
    account_num = models.CharField(
        max_length=50,
        verbose_name=_("Credit Collection Account Number"),
    )
    account_currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Account Currency"),
    )

    class Meta:
        verbose_name = _("Billing Department Account")
        verbose_name_plural = _("Billing Department Accounts")
        ordering = ["billing_department", "bank", "account_currency_id", "account_num"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_department", "bank", "account_currency", "account_num"],
                name="uniq_dept_bank_currency_account",
            )
        ]

    def __str__(self):
        ccy = getattr(self.account_currency, "code", None) or "-"
        return f"{self.billing_department.name} - {self.get_bank_display()} - {ccy}"


class RevenueSource(TimeStampedModel, models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Revenue Source Name"))
    gfs_code = models.CharField(max_length=20, verbose_name=_("GFS Code"))
    category = models.CharField(max_length=255, verbose_name=_("Revenue Category"))
    sub_category = models.CharField(
        max_length=255, verbose_name=_("Revenue Sub-Category")
    )

    class Meta:
        verbose_name = _("Revenue Source")
        verbose_name_plural = _("Revenue Sources")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.gfs_code}"


class RevenueSourceItem(TimeStampedModel, models.Model):
    """Revenue Source Item Line."""

    # Currency Codes
    CURRENCY_CHOICES = (
        ("TZS", _("Tanzanian Shilling")),
        ("USD", _("United States Dollar")),
    )

    rev_src = models.ForeignKey(
        RevenueSource, on_delete=models.CASCADE, verbose_name=_("Revenue Source")
    )
    description = models.CharField(
        max_length=255, verbose_name=_("Description"), help_text="Item Description"
    )
    amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Item Amount")
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="TZS",
        verbose_name=_("Currency Code"),
    )

    class Meta:
        verbose_name = _("Revenue Source Item")
        verbose_name_plural = _("Revenue Source Items")
        ordering = ["rev_src"]

    def __str__(self):
        return self.description

    @classmethod
    def get_item(cls, description):
        try:
            item = cls.objects.get(description=description)
            return item
        except cls.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        # Ensure amt updates create a new entry in the RevenueSourceItemPriceHistory table.
        # IMPORTANT: save the item first so the FK can be written safely.
        create_history = False
        if self.pk:
            original_item = RevenueSourceItem.objects.get(pk=self.pk)
            create_history = original_item.amt != self.amt
        else:
            create_history = True

        super().save(*args, **kwargs)

        if create_history:
            RevenueSourceItemPriceHistory.objects.create(
                rev_src_itm=self,
                amt=self.amt,
                effective_date=timezone.now(),
            )


class RevenueSourceItemPriceHistory(TimeStampedModel, models.Model):
    """Revenue Source Item Price History."""

    rev_src_itm = models.ForeignKey(
        RevenueSourceItem,
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name=_("Revenue Source Item"),
    )
    amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Item Amount")
    )
    effective_date = models.DateTimeField(verbose_name=_("Effective Date"))

    class Meta:
        verbose_name = _("Revenue Source Item Price History")
        verbose_name_plural = _("Revenue Source Item Price Histories")
        ordering = ["-effective_date"]

    def __str__(self):
        return (
            f"{self.rev_src_itm.description} - {self.amt} (from {self.effective_date})"
        )


class Bill(TimeStampedModel, models.Model):
    """Billing Invoice."""

    PAY_OPTIONS = (
        (1, _("FULL Bill")),
        (2, _("PARTIAL Bill")),
        (3, _("EXACT Bill")),
        (4, _("INFINITY payment option")),
        (5, _("LIMITED payment option")),
    )

    PAY_LIMITATION_TYPES = (
        (1, _("Normal Payment (No limitation)")),
        (2, _("All Commercial Bank Payment Limitation")),
        (3, _("Central Bank Limitation")),
        (4, _("Central Bank and Specific Commercial Bank Limitation")),
        (5, _("Specific Commercial Bank Limitation")),
    )

    PAY_PLANS = (
        (1, _("POST-PAID")),
        (2, _("PRE-PAID")),
    )

    BILL_TYPES = (
        (1, _("Normal Bill Control Number")),
        (2, _("Combined Bill Control Number")),
    )

    PAYMENT_TYPES = (
        (1, _("Pay All Bill Control Numbers At Once")),
        (2, _("Pay any Bill Control Number")),
    )

    CURRENCY_CHOICES = (
        ("TZS", _("Tanzanian Shilling")),
        ("USD", _("United States Dollar")),
    )

    sys_info = models.ForeignKey(
        SystemInfo,
        on_delete=models.SET_NULL,
        verbose_name=_("Integrating System Information"),
        help_text="The integrating system that generated the bill",
        blank=True,
        null=True,
    )
    bill_id = models.CharField(
        max_length=100,
        verbose_name=_("Bill ID"),
        help_text=_(
            "Unique identification of the Bill in Service Provider Billing System"
        ),
        unique=True,
    )
    grp_bill_id = models.CharField(
        max_length=100,
        verbose_name=_("Group Bill ID"),
        help_text=_(
            "Unique identification of the Group Bill in Service Provider Billing System"
        ),
        unique=True,
    )
    dept = models.ForeignKey(
        BillingDepartment,
        on_delete=models.CASCADE,
        verbose_name=_("Billing Department"),
    )
    type = models.PositiveSmallIntegerField(
        choices=BILL_TYPES, verbose_name=_("Bill Type"), default=1
    )
    pay_type = models.PositiveSmallIntegerField(
        choices=PAYMENT_TYPES, verbose_name=_("Payment Type"), default=2
    )
    description = models.TextField(
        blank=True, null=True, verbose_name=_("Bill Description")
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, verbose_name=_("Customer")
    )
    amt = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        verbose_name=_("Bill Amount"),
        null=True,
        blank=True,
    )
    eqv_amt = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        verbose_name=_("Bill Equivalent Amount"),
        null=True,
        blank=True,
    )
    min_amt = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Minimum Payment Amount"),
        help_text="The minimum amount payable value",
    )
    max_amt = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Payment Limitation Amount"),
        help_text="The maximum limitation value for a transaction",
    )
    pay_lim_type = models.PositiveSmallIntegerField(
        choices=PAY_LIMITATION_TYPES,
        verbose_name=_("Bill Payment Limitation Type"),
        default=1,
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        verbose_name=_("Currency Code"),
    )
    exch_rate = models.DecimalField(max_digits=32, decimal_places=2, default=1.00)
    pay_opt = models.PositiveSmallIntegerField(choices=PAY_OPTIONS, default=3)
    pay_plan = models.PositiveSmallIntegerField(
        choices=PAY_PLANS, default=1, verbose_name=_("Payment Plan")
    )
    gen_date = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Bill Issue Date"),
        help_text="The date when the bill was generated",
    )
    expr_date = models.DateTimeField(
        verbose_name=_("Bill Expiry Date"),
        help_text="The date when the bill will expire",
    )
    gen_by = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Bill Generated By")
    )
    appr_by = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Bill Approved By")
    )
    cntr_num = models.BigIntegerField(
        blank=True, null=True, verbose_name=_("Bill Control Number"), unique=True
    )

    class Meta:
        verbose_name = _("Bill")
        verbose_name_plural = _("Bills")
        ordering = ["-gen_date"]

    def __str__(self):
        return f"Bill {self.bill_id} for {self.customer.get_name()}"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        old_currency = None

        # Check for existing instance to detect currency change
        if not is_new:
            old_currency = Bill.objects.get(pk=self.pk).currency

        # Set the bill id and expiry date for new bills
        if is_new:
            # Set the bill generation date to the current date
            self.gen_date = timezone.now()

            # Generate the bill ID using the department code and the generation date
            self.bill_id = f"{self.dept.service_provider.code[-3:]}{self.gen_date.strftime('%Y%m%d%H%M%S')}"
            self.grp_bill_id = self.bill_id

        # Set the bill expiry date to 90 days from the generation date
        self.expr_date = self.gen_date + timezone.timedelta(days=90)

        super(Bill, self).save(*args, **kwargs)

        # Handle currency change for existing bills
        if old_currency and old_currency != self.currency and self.currency == "TZS":
            for item in self.billitem_set.all():
                # Check if bill item currency is different from the bill currency
                if item.rev_src_itm.currency != self.currency:
                    # Get the exchange rate for the bill currency and convert the amount
                    exchange_rate = ExchangeRate.objects.filter(
                        currency__code=item.rev_src_itm.currency
                    ).latest("trx_date")
                    item.amt = item.amt * exchange_rate.selling
                    item.save()

    def recalculate_amounts(self):
        items = list(self.billitem_set.select_related("rev_src_itm").all())
        for item in items:
            item.save()

        total = sum(item.amt for item in items)
        self.amt = total
        self.eqv_amt = total
        self.min_amt = total
        self.max_amt = total
        Bill.objects.filter(pk=self.pk).update(
            amt=total, eqv_amt=total, min_amt=total, max_amt=total
        )

    def get_absolute_url(self):
        return reverse("billing:bill-detail", kwargs={"pk": self.pk})

    def get_update_url(self):
        return reverse("billing:bill-update", kwargs={"pk": self.pk})

    def get_delete_url(self):
        return reverse("billing:bill-delete", kwargs={"pk": self.pk})

    def get_print_url(self):
        return reverse("billing:bill-print", kwargs={"pk": self.pk})

    def get_transfer_print_url(self):
        if self.cntr_num:
            return reverse("billing:bill-transfer-print", kwargs={"pk": self.pk})
        return None

    def get_receipt_print_url(self):
        if self.is_paid():
            return reverse("billing:bill-receipt-print", kwargs={"pk": self.pk})
        return None

    def service_provider(self):
        return self.dept.service_provider

    def payment_ref(self):
        return f"{self.billitem_set.first().rev_src_itm.rev_src.name}"

    def payer_name(self):
        return self.customer.get_name()

    def billed_items(self):
        count = self.billitem_set.count()
        if count == 1:
            return {
                "count": count,
                "description": f"{self.billitem_set.first().rev_src_itm.description} - {self.payment_ref()}",
                "amount": self.billitem_set.first().amt,
            }

        return {
            "count": count,
            "items": [
                {
                    "description": f"{item.rev_src_itm.description} - {self.payment_ref()}",
                    "amount": item.amt,
                }
                for item in self.billitem_set.all()
            ],
        }

    def amount_in_words(self):
        p = inflect.engine()
        # Convert the amount to integer
        amt_int = int(self.amt)
        # Convert the amount to words and capitalize each word
        amt_words = p.number_to_words(amt_int).title()
        return f"{amt_words} {self.get_currency_display()}."

    def is_cancelled(self):
        return (
            hasattr(self, "cancelledbill") and self.cancelledbill.status == "CANCELLED"
        )

    def is_paid(self):
        return hasattr(self, "payment")

    def is_reconciled(self):
        return hasattr(self, "paymentreconciliation")

    def get_cntr_num_request_status(self):
        """Return the status of the control number request."""
        try:
            log = PaymentGatewayLog.objects.filter(bill=self, req_type="1").latest(
                "created_at"
            )
            return {"status": log.status, "status_desc": log.status_desc}
        except PaymentGatewayLog.DoesNotExist:
            return {
                "status": "NOT FOUND",
                "status_desc": "Control Number Request Not Found",
            }


class BillItem(TimeStampedModel, models.Model):
    """Bill Item Line."""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, verbose_name=_("Bill"))
    dept = models.ForeignKey(
        BillingDepartment,
        on_delete=models.CASCADE,
        verbose_name=_("Billing Department"),
        help_text="The billing department that issued the bill",
    )
    rev_src_itm = models.ForeignKey(
        RevenueSourceItem, on_delete=models.CASCADE, verbose_name=_("Revenue Source")
    )
    ref_on_pay = models.CharField(
        max_length=1,
        default="N",
        verbose_name=_("Use Item Reference on Payment"),
        help_text="The value should be “N”",
    )
    description = models.CharField(
        max_length=255, verbose_name=_("Description"), help_text="Item Description"
    )
    qty = models.PositiveIntegerField(default=1, verbose_name=_("Bill Item Quantity"))
    amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Bill Item Amount")
    )
    eqv_amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Bill Item Equivalent Amount")
    )
    misc_amt = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Bill Item Miscellaneous Amount"),
    )
    penalty_amt = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Bill Item Penalty Amount"),
    )

    class Meta:
        verbose_name = _("Bill Item")
        verbose_name_plural = _("Bill Items")
        ordering = ["bill"]

    def __str__(self):
        return self.description

    def convert_usd_to_tzs(self, usd_amt):
        exchange_rate = ExchangeRate.objects.filter(currency__code="USD").latest(
            "trx_date"
        )
        return usd_amt * exchange_rate.selling

    def save(self, *args, **kwargs):
        self.description = self.rev_src_itm.description
        if self.penalty_amt > 0:
            self.amt = (self.qty * self.rev_src_itm.amt) + self.penalty_amt
        else:
            self.amt = self.qty * self.rev_src_itm.amt

        # Check if bill item currency is different from the bill currency
        if (
            self.bill.currency != self.rev_src_itm.currency
            and self.bill.currency == "TZS"
        ):
            # Get the exchange rate for the bill currency and convert the amount
            exchange_rate = ExchangeRate.objects.filter(
                currency__code=self.rev_src_itm.currency
            ).latest("trx_date")
            self.amt = self.amt * exchange_rate.selling

        self.eqv_amt = self.amt
        self.misc_amt = self.amt
        super(BillItem, self).save(*args, **kwargs)


class Payment(TimeStampedModel, models.Model):
    """Bill Payment Information."""

    bill = models.OneToOneField(
        Bill, on_delete=models.CASCADE, verbose_name=_("Bill"), primary_key=True
    )
    cust_cntr_num = models.BigIntegerField(verbose_name=_("Customer Control Number"))
    psp_code = models.CharField(
        max_length=10, verbose_name=_("Payment Service Provider Code")
    )
    psp_name = models.CharField(
        max_length=200, verbose_name=_("Payment Service Provider Name")
    )
    trx_id = models.CharField(
        max_length=100,
        verbose_name=_("Payment Service Provider Transaction ID"),
        null=True,
        blank=True,
    )
    payref_id = models.CharField(
        max_length=100, verbose_name=_("Payment receipt issued by GEPG")
    )
    bill_amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Bill Amount")
    )
    paid_amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Amount Paid")
    )
    currency = models.CharField(max_length=3, verbose_name=_("Paid amount currency"))
    coll_acc_num = models.CharField(
        max_length=50, verbose_name=_("Credited Collection Account Number")
    )
    trx_date = models.DateTimeField(verbose_name=_("Transaction Date"))
    pay_channel = models.CharField(
        max_length=50,
        verbose_name=_("Payment provider payment channel used to pay the bill"),
    )
    trdpty_trx_id = models.CharField(
        max_length=50,
        verbose_name=_("Third Party Transaction ID"),
        help_text=_(
            "Third Party Receipt such as Issuing Bank authorization Identification, MNO Receipt, Aggregator Receipt etc."
        ),
        null=True,
        blank=True,
    )
    pyr_name = models.CharField(
        max_length=200,
        verbose_name=_("Payer Name"),
        help_text="Payer Name as received from payment service provider",
        blank=True,
        null=True,
    )
    pyr_cell_num = models.CharField(
        max_length=12,
        verbose_name=_("Payer Cell Number"),
        help_text="Payer Mobile/Cell Number should have twelve digits including country code e.g. 255XXXXXXXXX",
        blank=True,
        null=True,
    )
    pyr_email = models.EmailField(verbose_name=_("Payer Email"), blank=True, null=True)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-trx_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["cust_cntr_num", "bill"],
                name="unique_payment",
            ),
        ]

    def __str__(self):
        return f"Payment for Bill ID - {self.bill.bill_id}, Control Number - {self.bill.cntr_num} paid. PayRef - {self.payref_id}"

    def paid_amount_in_words(self):
        p = inflect.engine()
        # Convert the amount to integer
        amt_int = int(self.paid_amt)
        # Convert the amount to words and capitalize each word
        amt_words = p.number_to_words(amt_int).title()
        return f"{amt_words} {self.bill.get_currency_display()}."

    def payment_ref(self):
        return f"{self.bill.billitem_set.first().rev_src_itm.rev_src.name}"

    def issuer_name(self):
        return self.bill.dept.service_provider.name


class PaymentReconciliation(TimeStampedModel, models.Model):
    """Payment Reconciliation Information."""

    # bill = models.ForeignKey(Bill, on_delete=models.CASCADE, verbose_name=_("Bill"))
    cust_cntr_num = models.BigIntegerField(verbose_name=_("Customer Control Number"))
    grp_bill_id = models.CharField(max_length=100, verbose_name=_("Group Bill ID"))
    sp_code = models.CharField(
        max_length=10, verbose_name=_("Service Provider Code"), blank=True, null=True
    )
    bill_id = models.CharField(max_length=100, verbose_name=_("Bill ID"))
    bill_ctr_num = models.BigIntegerField(verbose_name=_("Bill Control Number"))
    psp_code = models.CharField(
        max_length=10, verbose_name=_("Payment Service Provider Code")
    )
    psp_name = models.CharField(
        max_length=200, verbose_name=_("Payment Service Provider Name")
    )
    trx_id = models.CharField(
        max_length=100, verbose_name=_("Payment Service Provider Transaction ID")
    )
    payref_id = models.CharField(
        max_length=100, verbose_name=_("Payment receipt issued by GEPG")
    )
    bill_amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Bill Amount")
    )
    paid_amt = models.DecimalField(
        max_digits=32, decimal_places=2, verbose_name=_("Amount Paid")
    )
    bill_pay_opt = models.CharField(
        max_length=10, verbose_name=_("Bill Payment Option")
    )
    currency = models.CharField(max_length=3, verbose_name=_("Paid amount currency"))
    coll_acc_num = models.CharField(
        max_length=50, verbose_name=_("Credited Collection Account Number")
    )
    trx_date = models.DateTimeField(verbose_name=_("Transaction Date"))
    usd_pay_chnl = models.CharField(
        max_length=50,
        verbose_name=_("Payment provider payment channel used to pay the bill"),
    )
    trdpty_trx_id = models.CharField(
        max_length=50,
        verbose_name=_("Third Party Transaction ID"),
        help_text=_(
            "Third Party Receipt such as Issuing Bank authorization Identification, MNO Receipt, Aggregator Receipt etc."
        ),
        null=True,
        blank=True,
    )
    qt_ref_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_(
            "Unique Identification of quote transaction generated from PSP System"
        ),
    )
    pyr_name = models.CharField(
        max_length=200,
        verbose_name=_("Payer Name"),
        help_text="Payer Name as received from payment service provider",
        blank=True,
        null=True,
    )
    pyr_cell_num = models.CharField(
        max_length=12,
        verbose_name=_("Payer Cell Number"),
        help_text="Payer Mobile/Cell Number should have twelve digits including country code e.g. 255XXXXXXXXX",
        blank=True,
        null=True,
    )
    pyr_email = models.EmailField(verbose_name=_("Payer Email"), blank=True, null=True)

    class Meta:
        verbose_name = _("Payment Reconciliation")
        verbose_name_plural = _("Payment Reconciliations")
        ordering = ["trx_date"]

    def __str__(self):
        return f"Payment Reconciliation for Bill ID - {self.bill_id}, Control Number - {self.cust_cntr_num} paid. Amount - {self.paid_amt}"


class PaymentGatewayLog(TimeStampedModel, models.Model):
    """Payment Gateway communication log information."""

    STATUS_CHOICES = (
        ("PENDING", _("Pending")),
        ("SUCCESS", _("Success")),
        ("ERROR", _("Error")),
        ("RETRYING", _("Retrying")),
        ("FAILED", _("Failed")),
        ("CANCELLED", _("Cancelled")),  # Cancelled by the user
    )

    REQ_TYPE_CHOICES = (
        ("1", _("Bill Control Number Request")),
        ("2", _("Bill Control Number Reuse Request")),
        ("3", _("Bill Control Number Change Request")),
        ("4", _("Bill Control Number Cancellation Request")),
        ("5", _("BILL Payment Notification Request")),
        ("6", _("BILL Payment Reconciliation Request")),
        ("7", _("BILL Cancellation Request")),
    )

    sys_info = models.ForeignKey(
        SystemInfo,
        on_delete=models.SET_NULL,
        verbose_name=_("Integrating System Information"),
        blank=True,
        null=True,
    )
    bill = models.ForeignKey(
        Bill,
        on_delete=models.SET_NULL,
        verbose_name=_("Bill"),
        blank=True,
        null=True,
    )
    req_id = models.CharField(
        max_length=100,
        verbose_name=_("Request ID"),
    )
    req_type = models.CharField(
        max_length=1,
        choices=REQ_TYPE_CHOICES,
        verbose_name=_("Request Type"),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        verbose_name=_("Request Status"),
        default="PENDING",  # Default to PENDING when the log is created
    )
    status_desc = models.TextField(
        verbose_name=_("Request Status Description"),
        blank=True,
        null=True,
    )
    req_data = models.JSONField(
        verbose_name=_("Request Data"),
        blank=True,
        default=dict,
    )
    req_ack = models.JSONField(
        verbose_name=_("Request Acknowledgement"),
        blank=True,
        default=dict,
    )
    res_data = models.JSONField(
        verbose_name=_("Response Data"),
        blank=True,
        default=dict,
    )
    res_ack = models.JSONField(
        verbose_name=_("Response Acknowledgement"),
        blank=True,
        default=dict,
    )

    class Meta:
        verbose_name = _("Payment Gateway Log")
        verbose_name_plural = _("Payment Gateway Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["req_id"], name="req_id_idx"),
            models.Index(fields=["bill"], name="bill_idx"),
            models.Index(fields=["status"], name="status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["req_id", "req_type"],
                name="unique_request_id",
            ),
        ]

    def __str__(self):
        return f"{self.req_id} - {self.get_req_type_display()} - {self.status} - {self.status_desc}"

    def control_number_request_status(self):
        """Return the status of the control number request."""
        if self.req_type == "1":
            return self.status


class CancelledBill(TimeStampedModel, models.Model):
    """Cancelled Bill Information."""

    CANCEL_STATUS = (
        ("PENDING", _("Pending")),
        ("CANCELLED", _("Cancelled")),
        ("FAILED", _("Failed")),
        ("RECREATED", _("Recreated")),
    )

    bill = models.OneToOneField(
        Bill,
        on_delete=models.CASCADE,
        verbose_name=_("Cancelled Bill"),
        primary_key=True,
    )
    cust_cntr_num = models.BigIntegerField(
        verbose_name=_("Cancelled Customer Control Number"),
        blank=True,
        null=True,
    )
    reason = models.TextField(
        verbose_name=_("Cancellation Reason"),
        help_text="Reason for cancelling the bill",
    )
    status = models.CharField(
        max_length=10,
        choices=CANCEL_STATUS,
        verbose_name=_("Cancellation Status"),
        default="PENDING",
    )
    gen_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cancelled_bill_generated_by",
        verbose_name=_("Cancelled By"),
    )
    appr_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cancelled_bill_approved_by",
        verbose_name=_("Approved By"),
    )

    class Meta:
        verbose_name = _("Cancelled Bill")
        verbose_name_plural = _("Cancelled Bills")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cancelled Bill - {self.bill.bill_id if self.bill else 'N/A'}"


class BillingEmailDelivery(TimeStampedModel, models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ("INVOICE", _("Invoice")),
        ("RECEIPT", _("Receipt")),
    )

    STATUS_CHOICES = (
        ("NOT_SENT", _("Not sent")),
        ("PENDING", _("Pending")),
        ("SENT", _("Sent")),
        ("FAILED", _("Failed")),
    )

    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name="email_deliveries",
        verbose_name=_("Bill"),
    )
    document_type = models.CharField(
        max_length=10,
        choices=DOCUMENT_TYPE_CHOICES,
        verbose_name=_("Document type"),
    )
    recipient_email = models.EmailField(verbose_name=_("Recipient email"))
    event_key = models.CharField(
        max_length=100,
        verbose_name=_("Event key"),
        help_text=_(
            "Idempotency key for the triggering event (e.g., auto:payment_confirmed, manual:{uuid})"
        ),
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING",
        verbose_name=_("Status"),
    )
    attempt_count = models.PositiveIntegerField(default=0, verbose_name=_("Attempts"))
    enqueued_at = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Enqueued at")
    )
    last_attempt_at = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Last attempt at")
    )
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Sent at"))
    failure_reason = models.TextField(
        blank=True, null=True, verbose_name=_("Failure reason")
    )

    class Meta:
        verbose_name = _("Billing Email Delivery")
        verbose_name_plural = _("Billing Email Deliveries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["bill"], name="bed_bill_idx"),
            models.Index(fields=["status"], name="bed_status_idx"),
            models.Index(fields=["document_type"], name="bed_doc_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bill", "document_type", "recipient_email", "event_key"],
                name="uniq_bed_bill_doc_recipient_event",
            ),
        ]

    def __str__(self):
        return (
            f"{self.document_type} delivery for {self.bill.bill_id} to {self.recipient_email} "
            f"({self.status})"
        )
