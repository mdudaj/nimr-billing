from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SystemInfo(TimeStampedModel, models.Model):
    """Integrating System's Information."""

    code = models.CharField(
        max_length=50, unique=True, verbose_name="Integrating System Code",
    )
    name = models.CharField(max_length=200, verbose_name="Intergating System Name",)
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
        return f"{self.first_name} {self.middle_name} {self.last_name}"

    def get_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}"


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
    """Billing Department Collection Center."""

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
    account_num = models.CharField(
        max_length=50,
        verbose_name=_("Credit Collection Account Number"),
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
    description = models.CharField(
        max_length=500, blank=True, null=True, verbose_name=_("Bill Description")
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
        default="TZS",
        verbose_name=_("Currency Code"),
    )
    exch_rate = models.DecimalField(max_digits=32, decimal_places=2, default=1.00)
    pay_opt = models.PositiveSmallIntegerField(choices=PAY_OPTIONS, default=3)
    pay_plan = models.PositiveSmallIntegerField(
        choices=PAY_PLANS, default=1, verbose_name=_("Payment Plan")
    )
    gen_date = models.DateTimeField(
        auto_now_add=True,
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
        ordering = ["gen_date"]

    def __str__(self):
        return f"Bill {self.bill_id} for {self.customer.get_name()}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.gen_date = timezone.now()

        # Set the bill expiry date to 30 days from the generation date
        self.expr_date = self.gen_date + timezone.timedelta(days=30)

        # Bill ID and Group Bill ID
        self.bill_id = f"{self.dept.code}{self.gen_date.strftime('%Y%m%d%H%M%S')}"
        self.grp_bill_id = self.bill_id

        super(Bill, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("billing:bill-detail", kwargs={"pk": self.pk})

    def get_update_url(self):
        return reverse("billing:bill-update", kwargs={"pk": self.pk})

    def get_delete_url(self):
        return reverse("billing:bill-delete", kwargs={"pk": self.pk})

    def get_print_url(self):
        return reverse("billing:bill-print", kwargs={"pk": self.pk})


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

    class Meta:
        verbose_name = _("Bill Item")
        verbose_name_plural = _("Bill Items")
        ordering = ["bill"]

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        self.description = self.rev_src_itm.description
        self.amt = self.qty * self.rev_src_itm.amt
        self.eqv_amt = self.amt
        self.misc_amt = self.amt
        super(BillItem, self).save(*args, **kwargs)


class Payment(TimeStampedModel, models.Model):
    """Bill Payment Information."""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, verbose_name=_("Bill"))
    cust_cntr_num = models.BigIntegerField(
        verbose_name=_("Customer Control Number")
    )
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
        ordering = ["trx_date"]

    def __str__(self):
        return f"Payment for Bill ID - {self.bill.bill_id}, Control Number - {self.bill.cntr_num} paid. Amount - {self.paid_amt}"


class PaymentReconciliation(TimeStampedModel, models.Model):
    """Payment Reconciliation Information."""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, verbose_name=_("Bill"))
    cust_cntr_num = models.BigIntegerField(
        verbose_name=_("Customer Control Number")
    )
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
    pay_status = models.CharField(
        max_length=500,
        verbose_name=_("Payment Reconciliation Status"),
        help_text=_("Reconciliation Status Description"),
    )

    class Meta:
        verbose_name = _("Payment Reconciliation")
        verbose_name_plural = _("Payment Reconciliations")
        ordering = ["trx_date"]

    def __str__(self):
        return f"Payment Reconciliation for Bill ID - {self.bill.bill_id}, Control Number - {self.cust_cntr_num} paid. Amount - {self.paid_amt}"


class PaymentGatewayLog(TimeStampedModel, models.Model):
    """Payment Gateway communication log information."""

    REQ_TYPE_CHOICES = (
        ("1", _("Bill Control Number Request")),
        ("2", _("Bill Control Number Reuse Request")),
        ("3", _("Bill Control Number Change Request")),
        ("4", _("Bill Control Number Cancellation Request")),
        ("5", _("BILL Payment Notification Request")),
        ("6", _("BILL Payment Reconciliation Request")),
    )

    sys_info = models.ForeignKey(
        SystemInfo, 
        on_delete=models.CASCADE, 
        verbose_name=_("Integrating System Information"), 
        blank=True, 
        null=True,
        )
    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        verbose_name=_("Bill"),
        blank=True,
        null=True,
    )
    req_id = models.CharField(
        max_length=100,
        verbose_name=_("Request ID"),
        unique=True,
    )
    req_type = models.CharField(
        max_length=1,
        choices=REQ_TYPE_CHOICES,
        verbose_name=_("Request Type"),
    )
    status = models.CharField(
        max_length=50,
        verbose_name=_("Request Status"),
    )
    status_desc = models.CharField(
        max_length=255,
        verbose_name=_("Request Status Description"),
    )
    req_data = models.JSONField(
        verbose_name=_("Request Data"),
        blank=True,
        null=True,
    )
    req_ack = models.JSONField(
        verbose_name=_("Request Acknowledgement"),
        blank=True,
        null=True,
    )
    res_data = models.JSONField(
        verbose_name=_("Response Data"),
        blank=True,
        null=True,
    )
    res_ack = models.JSONField(
        verbose_name=_("Response Acknowledgement"),
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Payment Gateway Log")
        verbose_name_plural = _("Payment Gateway Logs")
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.req_id} - {self.get_req_type_display()} - {self.bill.bill_id}: {self.status} - {self.status_desc}"
            
        )
