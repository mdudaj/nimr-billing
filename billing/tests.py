from decimal import Decimal

from billing.models import (
    Bill,
    Customer,
    BillingDepartment,
    ServiceProvider,
    RevenueSource,
    RevenueSourceItem,
    BillItem,
    Currency,
    ExchangeRate,
)

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class BillCurrencyTestCase(TestCase):
    def setUp(self):
        # Setup test data

        # Create Customer
        self.customer = Customer.objects.create(
            first_name="John",
            middle_name="A.",
            last_name="Doe",
            tin="123456789",
            id_num="1234567890123456",
            id_type="1",
            account_num="9876543210",
            cell_num="255700000000",
            email="john.doe@example.com",
        )

        # Create ServiceProvider
        self.service_provider = ServiceProvider.objects.create(
            name="Test Service Provider",
            code="SP001",
            grp_code="SP001",
            sys_code="SYS001",
        )

        # Create BillingDepartment
        self.billing_dept = BillingDepartment.objects.create(
            service_provider=self.service_provider,
            name="Test Department",
            description="This is a test billing department",
            code="DEPT001",
            account_num="1234567890123456",
        )

        # Create RevenueSource
        self.revenue_source = RevenueSource.objects.create(
            name="Revenue Source 1",
            gfs_code="GFS001",
            category="Category A",
            sub_category="Sub-category A1",
        )

        # Create RevenueSourceItem
        self.revenue_source_item = RevenueSourceItem.objects.create(
            rev_src=self.revenue_source,
            description="Revenue Source Item 1",
            amt=1000.00,
            currency="TZS",
        )

    def test_valid_currency_tzs(self):
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.billing_dept,
            currency="TZS",
            amt=1000,
        )
        self.assertEqual(bill.currency, "TZS")

    def test_valid_currency_usd(self):
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.billing_dept,
            currency="USD",
            amt=1000,
        )
        self.assertEqual(bill.currency, "USD")

    def test_invalid_currency(self):
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.billing_dept,
            currency="EUR",  # Invalid currency
            amt=1000,
        )
        with self.assertRaises(ValidationError):
            bill.full_clean()


class BillCurrencyConversionTestCase(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            first_name="Jane",
            middle_name="B.",
            last_name="Doe",
            tin="123456789",
            id_num="1234567890123456",
            id_type="1",
            account_num="9876543210",
            cell_num="255700000000",
            email="jane.doe@example.com",
        )

        self.service_provider = ServiceProvider.objects.create(
            name="Test Service Provider",
            code="SP002",
            grp_code="SP002",
            sys_code="SYS002",
        )

        self.billing_dept = BillingDepartment.objects.create(
            service_provider=self.service_provider,
            name="Test Department",
            description="This is a test billing department",
            code="DEPT002",
            account_num="1234567890123456",
        )

        self.revenue_source = RevenueSource.objects.create(
            name="Revenue Source USD",
            gfs_code="GFS002",
            category="Category B",
            sub_category="Sub-category B1",
        )

        self.revenue_source_item_usd = RevenueSourceItem.objects.create(
            rev_src=self.revenue_source,
            description="Revenue Source Item USD",
            amt=Decimal("10.00"),
            currency="USD",
        )

        self.currency_usd = Currency.objects.create(code="USD", name="US Dollar")
        ExchangeRate.objects.create(
            currency=self.currency_usd,
            trx_date=timezone.now().date(),
            buying=Decimal("2400.00"),
            selling=Decimal("2500.00"),
        )

    def test_recalculate_amounts_converts_usd_to_tzs(self):
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.billing_dept,
            currency="TZS",
            amt=0,
        )

        item = BillItem.objects.create(
            bill=bill,
            dept=self.billing_dept,
            rev_src_itm=self.revenue_source_item_usd,
        )

        bill.recalculate_amounts()

        item.refresh_from_db()
        bill.refresh_from_db()

        self.assertEqual(item.amt, Decimal("25000.00"))
        self.assertEqual(bill.amt, Decimal("25000.00"))


class BillViewCurrencyConversionTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="viewuser@example.com", password="password"
        )
        self.customer = Customer.objects.create(
            first_name="View",
            middle_name="C.",
            last_name="User",
            tin="123456789",
            id_num="1234567890123456",
            id_type="1",
            account_num="9876543210",
            cell_num="255700000000",
            email="view.user@example.com",
        )
        self.service_provider = ServiceProvider.objects.create(
            name="Test Service Provider",
            code="SPV01",
            grp_code="SPV01",
            sys_code="SYSV01",
        )
        self.billing_dept = BillingDepartment.objects.create(
            service_provider=self.service_provider,
            name="View Department",
            description="View billing department",
            code="DEPTV01",
            account_num="1234567890123456",
        )
        self.revenue_source = RevenueSource.objects.create(
            name="Revenue Source USD",
            gfs_code="GFSV01",
            category="Category V",
            sub_category="Sub-category V1",
        )
        self.revenue_source_item_usd = RevenueSourceItem.objects.create(
            rev_src=self.revenue_source,
            description="Revenue Source Item USD",
            amt=Decimal("10.00"),
            currency="USD",
        )
        self.currency_usd = Currency.objects.create(code="USD", name="US Dollar")
        ExchangeRate.objects.create(
            currency=self.currency_usd,
            trx_date=timezone.now().date(),
            buying=Decimal("2400.00"),
            selling=Decimal("2500.00"),
        )

    def _bill_form_data(self, currency):
        return {
            "dept": self.billing_dept.pk,
            "type": 1,
            "pay_type": 2,
            "description": "Test Bill",
            "customer": self.customer.pk,
            "pay_lim_type": 1,
            "currency": currency,
            "exch_rate": "1.00",
            "pay_opt": 3,
            "pay_plan": 1,
            "gen_by": "",
            "appr_by": "",
        }

    def _billitem_formset_data(self, item=None):
        data = {
            "billitem_set-TOTAL_FORMS": "1",
            "billitem_set-INITIAL_FORMS": "0",
            "billitem_set-MIN_NUM_FORMS": "0",
            "billitem_set-MAX_NUM_FORMS": "1000",
            "billitem_set-0-dept": str(self.billing_dept.pk),
            "billitem_set-0-rev_src_itm": str(self.revenue_source_item_usd.pk),
            "billitem_set-0-qty": "1",
            "billitem_set-0-ref_on_pay": "N",
            "billitem_set-0-penalty_amt": "0.00",
        }
        if item is not None:
            data["billitem_set-INITIAL_FORMS"] = "1"
            data["billitem_set-0-id"] = str(item.pk)
        return data

    @patch("billing.views.send_bill_control_number_request.delay")
    def test_bill_create_view_converts_usd_to_tzs(self, delay_mock):
        self.client.force_login(self.user)
        data = {**self._bill_form_data("TZS"), **self._billitem_formset_data()}
        response = self.client.post(reverse("billing:bill-create"), data)
        self.assertEqual(response.status_code, 302)

        bill = Bill.objects.get(customer=self.customer)
        item = bill.billitem_set.first()

        self.assertEqual(item.amt, Decimal("25000.00"))
        self.assertEqual(bill.amt, Decimal("25000.00"))

    @patch("billing.views.send_bill_control_number_request.delay")
    def test_bill_update_view_converts_usd_to_tzs(self, delay_mock):
        self.client.force_login(self.user)
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.billing_dept,
            currency="USD",
            amt=0,
        )
        item = BillItem.objects.create(
            bill=bill,
            dept=self.billing_dept,
            rev_src_itm=self.revenue_source_item_usd,
        )

        data = {
            **self._bill_form_data("TZS"),
            **self._billitem_formset_data(item=item),
        }
        response = self.client.post(
            reverse("billing:bill-update", args=[bill.pk]), data
        )
        self.assertEqual(response.status_code, 302)

        bill.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(bill.currency, "TZS")
        self.assertEqual(item.amt, Decimal("25000.00"))
        self.assertEqual(bill.amt, Decimal("25000.00"))
