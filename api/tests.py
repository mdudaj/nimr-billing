from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_api_key.models import APIKey

from billing.models import (
    Bill,
    BillingDepartment,
    Currency,
    Customer,
    RevenueSource,
    RevenueSourceItem,
    ServiceProvider,
    SystemInfo,
)

from .models import BillCntrlNum, BillPayment
from .serializers import BillSerializer


class BillingFixtureMixin:
    def create_billing_fixtures(self):
        self.currency = Currency.objects.create(code="TZS", name="Tanzanian Shilling")

        self.system_info = SystemInfo.objects.create(
            code="SYS001",
            name="Test System",
            cntrnum_response_callback="https://example.com/cntrl",
            pay_notification_callback="https://example.com/pay",
        )

        self.service_provider = ServiceProvider.objects.create(
            name="Test SP",
            code="SPC123",
            grp_code="GRP123",
            sys_code="SYS",
        )

        self.billing_dept = BillingDepartment.objects.create(
            service_provider=self.service_provider,
            name="Finance",
            description="Finance Dept",
            code="FIN",
            bank="CRDB",
            bank_swift_code="CRDBTZTZ",
            account_num="000000000000",
            account_currency=self.currency,
        )

        self.rev_src = RevenueSource.objects.create(
            name="Revenue",
            gfs_code="GFS",
            category="CAT",
            sub_category="SUB",
        )

        self.revenue_source_item = RevenueSourceItem.objects.create(
            rev_src=self.rev_src,
            description="Revenue Item",
            amt="100.00",
            currency="TZS",
        )

        self.valid_customer_data = {
            "first_name": "John",
            "middle_name": "Doe",
            "last_name": "Smith",
            "cell_num": "255123456789",
            "email": "john.smith@example.com",
        }

        self.invalid_customer_data = {
            "first_name": "John",
            "last_name": "Smith",
            "cell_num": "255123456789",
            "email": "invalid-email",
        }


class BillSerializerTest(BillingFixtureMixin, TestCase):
    def setUp(self):
        self.create_billing_fixtures()

        self.valid_data = {
            "sys_code": "SYS001",
            "bill_dept": "Finance",
            "description": "Monthly subscription",
            "revenue_source": self.revenue_source_item.id,
            "customer": self.valid_customer_data,
        }

    def test_bill_creation_success(self):
        serializer = BillSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        bill = serializer.save()

        self.assertIsInstance(bill, Bill)
        self.assertEqual(bill.sys_info, self.system_info)
        self.assertEqual(bill.dept, self.billing_dept)
        self.assertEqual(bill.customer.email, "john.smith@example.com")
        self.assertEqual(str(bill.amt), "100.00")

    def test_invalid_customer_data(self):
        invalid_data = self.valid_data.copy()
        invalid_data["customer"] = self.invalid_customer_data

        serializer = BillSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("customer", serializer.errors)

    def test_nonexistent_sys_code(self):
        invalid_data = self.valid_data.copy()
        invalid_data["sys_code"] = "INVALID_SYS_CODE"

        serializer = BillSerializer(data=invalid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()
        self.assertIn("sys_code", str(ctx.exception))

    def test_nonexistent_bill_dept(self):
        invalid_data = self.valid_data.copy()
        invalid_data["bill_dept"] = "INVALID_DEPT"

        serializer = BillSerializer(data=invalid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()
        self.assertIn("bill_dept", str(ctx.exception))

    def test_nonexistent_revenue_source(self):
        invalid_data = self.valid_data.copy()
        invalid_data["revenue_source"] = 999999

        serializer = BillSerializer(data=invalid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError) as ctx:
            serializer.save()
        self.assertIn("revenue_source", str(ctx.exception))

    def test_update_not_supported(self):
        customer = Customer.objects.create(**self.valid_customer_data)
        bill = Bill.objects.create(
            sys_info=self.system_info,
            dept=self.billing_dept,
            customer=customer,
            currency="TZS",
            gen_by=customer.get_name(),
            appr_by=customer.get_name(),
        )

        serializer = BillSerializer(instance=bill, data=self.valid_data)
        with self.assertRaises(ValidationError) as context:
            serializer.update(bill, self.valid_data)

        self.assertIn("Update operation not supported", str(context.exception))


class ApiIdempotencyAndCallbacksTest(BillingFixtureMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.create_billing_fixtures()
        self.client = APIClient()
        api_key_obj, key = APIKey.objects.create_key(name="test-key")
        self.api_key = api_key_obj
        self.api_key_value = key
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {self.api_key_value}")

        self.bill_payload = {
            "sys_code": "SYS001",
            "bill_dept": "Finance",
            "description": "Monthly subscription",
            "revenue_source": self.revenue_source_item.id,
            "customer": self.valid_customer_data,
        }

    @patch("api.views.send_bill_control_number_request.delay")
    def test_bill_submission_is_idempotent_for_retries(self, delay_mock):
        url = "/api/bill-submission/"

        res1 = self.client.post(url, self.bill_payload, format="json")
        self.assertEqual(res1.status_code, 201, res1.data)
        self.assertIn("req_id", res1.data)
        self.assertIn("bill_id", res1.data)

        res2 = self.client.post(url, self.bill_payload, format="json")
        self.assertEqual(res2.status_code, 201, res2.data)

        self.assertEqual(res1.data["req_id"], res2.data["req_id"])
        self.assertEqual(res1.data["bill_id"], res2.data["bill_id"])

        # Ensure we didn't create duplicate bills.
        self.assertEqual(Bill.objects.count(), 1)
        delay_mock.assert_called_once()

    def test_control_number_callback_is_duplicate_safe(self):
        url = "/api/bill-cntrl-num-response-callback/"
        payload = {
            "req_id": "REQ1",
            "bill_id": "BILL1",
            "cntrl_num": "CNTRL1",
            "bill_amt": "100.00",
        }

        res1 = self.client.post(url, payload, format="json")
        self.assertEqual(res1.status_code, 200, res1.data)
        self.assertEqual(res1.data.get("duplicate"), False)

        res2 = self.client.post(url, payload, format="json")
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertEqual(res2.data.get("duplicate"), True)
        self.assertEqual(BillCntrlNum.objects.count(), 1)

    def test_payment_callback_is_duplicate_safe_by_trx_id(self):
        BillCntrlNum.objects.create(
            req_id="REQ1",
            bill_id="BILL1",
            cntrl_num="CNTRL1",
            bill_amt="100.00",
        )

        url = "/api/bill-cntrl-num-payment-callback/"
        payload = {
            "bill_id": "BILL1",
            "psp_code": "PSP",
            "psp_name": "Provider",
            "trx_id": "TRX123",
            "payref_id": "PAYREF",
            "bill_amt": "100.00",
            "paid_amt": "100.00",
            "paid_ccy": "TZS",
            "coll_acc_num": "000000",
            "trx_date": "2025-12-29T12:00:00Z",
            "pay_channel": "MOBILE",
            "pay_cell_num": "255123456789",
        }

        res1 = self.client.post(url, payload, format="json")
        self.assertEqual(res1.status_code, 200, res1.data)
        self.assertEqual(res1.data.get("duplicate"), False)
        self.assertEqual(BillPayment.objects.count(), 1)

        res2 = self.client.post(url, payload, format="json")
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertEqual(res2.data.get("duplicate"), True)
        self.assertEqual(BillPayment.objects.count(), 1)
