from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import (
    BillingDepartment,
    Currency,
    Customer,
    Payment,
    RevenueSource,
    RevenueSourceItem,
    ServiceProvider,
    Bill,
    BillItem,
)


class FinancialReportViewTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="reports@example.com", password="password"
        )

        self.tzs, _ = Currency.objects.get_or_create(
            code="TZS", defaults={"name": "Tanzanian Shilling"}
        )

        self.customer = Customer.objects.create(
            first_name="Jane",
            last_name="Doe",
            tin="123456789",
            id_num="1234567890123456",
            id_type="1",
            account_num="000000000000",
            cell_num="255700000000",
            email="jane.doe@example.com",
        )
        self.sp = ServiceProvider.objects.create(
            name="Test SP",
            code="SP001",
            grp_code="GRP001",
            sys_code="SYS001",
        )
        self.dept = BillingDepartment.objects.create(
            service_provider=self.sp,
            name="Center 1",
            description="Test Center",
            code="C001",
        )

        self.rev_src = RevenueSource.objects.create(
            name="Revenue",
            gfs_code="GFS001",
            category="CAT",
            sub_category="SUB",
        )
        self.rev_item = RevenueSourceItem.objects.create(
            rev_src=self.rev_src,
            description="Item 1",
            amt=Decimal("1000.00"),
            currency="TZS",
        )

        self.bill = Bill.objects.create(
            dept=self.dept,
            customer=self.customer,
            currency="TZS",
            description="Test bill",
        )
        BillItem.objects.create(bill=self.bill, dept=self.dept, rev_src_itm=self.rev_item)
        self.bill.recalculate_amounts()

        now = timezone.now()
        Payment.objects.create(
            bill=self.bill,
            cust_cntr_num=1234567890,
            psp_code="PSP",
            psp_name="PSP Name",
            trx_id="TRX001",
            payref_id="PAYREF001",
            bill_amt=self.bill.amt,
            paid_amt=self.bill.amt,
            currency="TZS",
            coll_acc_num="0150433049200",
            trx_date=now,
            pay_channel="BANK",
        )

    def test_financial_report_loads(self):
        self.client.login(email="reports@example.com", password="password")
        url = reverse("billing:financial-report")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_financial_report_custom_range_collections(self):
        self.client.login(email="reports@example.com", password="password")
        url = reverse("billing:financial-report")
        today = timezone.now().date()
        resp = self.client.get(
            url,
            {
                "period": "DR",
                "basis": "COLLECTIONS",
                "start_date": today.isoformat(),
                "end_date": today.isoformat(),
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["totals_by_currency"])
