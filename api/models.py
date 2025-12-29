from django.db import models


class ApiIdempotencyRecord(models.Model):
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_SUCCEEDED = "SUCCEEDED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = (
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    api_key_hash = models.CharField(max_length=64, db_index=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    bucket_start = models.DateTimeField(db_index=True)
    body_hash = models.CharField(max_length=64)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IN_PROGRESS,
        db_index=True,
    )

    # Persist the canonical response so retries can be served without duplicating work.
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)

    # Convenience fields for this API’s main flow.
    req_id = models.CharField(max_length=50, null=True, blank=True)
    bill_id = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_idempotency_record"
        constraints = [
            models.UniqueConstraint(
                fields=["api_key_hash", "method", "path", "bucket_start", "body_hash"],
                name="uniq_api_idempotency_key",
            )
        ]

    def __str__(self):
        return f"{self.method} {self.path} {self.status}"


class BillCntrlNum(models.Model):
    req_id = models.CharField(max_length=50, unique=True)
    bill_id = models.CharField(max_length=50, unique=True)
    cntrl_num = models.CharField(max_length=50, unique=True)
    bill_amt = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.req_id} - {self.bill_id} - {self.cntrl_num}"

    class Meta:
        db_table = "bill_cntrl_num"
        verbose_name = "Bill Control Number"
        verbose_name_plural = "Bill Control Numbers"


class BillPayment(models.Model):
    # Some gateways may send payment notifications before control-number callbacks.
    # Keep the string bill_id for correlation and allow bill_cntrl_num to be linked later.
    bill_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    bill_cntrl_num = models.ForeignKey(
        BillCntrlNum, on_delete=models.CASCADE, null=True, blank=True
    )
    psp_code = models.CharField(max_length=50)
    psp_name = models.CharField(max_length=50)
    trx_id = models.CharField(max_length=50, db_index=True)
    payref_id = models.CharField(max_length=50)
    bill_amt = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amt = models.DecimalField(max_digits=10, decimal_places=2)
    paid_ccy = models.CharField(max_length=3)
    coll_acc_num = models.CharField(max_length=50)
    trx_date = models.DateTimeField()
    pay_channel = models.CharField(max_length=50)
    pay_cell_num = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.bill_id or '-'} - {self.trx_id}: Paid {self.paid_amt} {self.paid_ccy}"

    class Meta:
        db_table = "bill_payment"
        verbose_name = "Bill Payment"
        verbose_name_plural = "Bill Payments"
        constraints = [
            models.UniqueConstraint(fields=["trx_id"], name="uniq_billpayment_trx_id"),
        ]
