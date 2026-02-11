from billing.models import (
    Bill,
    Customer,
    BillingDepartment,
    ServiceProvider,
    RevenueSource,
    RevenueSourceItem,
    BillItem,
)

from django.core.exceptions import ValidationError
from django.test import TestCase


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
