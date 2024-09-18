from django.db import models


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
    bill_cntrl_num = models.ForeignKey(BillCntrlNum, on_delete=models.CASCADE)
    psp_code = models.CharField(max_length=50)
    psp_name = models.CharField(max_length=50)
    trx_id = models.CharField(max_length=50)
    payref_id = models.CharField(max_length=50)
    bill_amt = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amt = models.DecimalField(max_digits=10, decimal_places=2)
    paid_ccy = models.CharField(max_length=3)
    coll_acc_num = models.CharField(max_length=50)
    trx_date = models.DateTimeField()
    pay_channel = models.CharField(max_length=50)
    pay_cell_num = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.bill} - {self.trx_id}: Paid {self.paid_amt} {self.paid_ccy}"
    
    class Meta:
        db_table = "bill_payment"
        verbose_name = "Bill Payment"
        verbose_name_plural = "Bill Payments"
