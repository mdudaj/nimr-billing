from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .models import (
    Bill,
    SystemInfo,
    BillingDepartment,
    Customer,
    RevenueSourceItem,
    BillItem,
)
from .serializers import BillSerializer


class BillSerializerTest(TestCase):

    def setUp(self):
        # Setup necessary objects
        self.system_info = SystemInfo.objects.create(code="SYS001")
        self.billing_dept = BillingDepartment.objects.create(name="Finance")
        self.revenue_source_item = RevenueSourceItem.objects.create(
            id=1, name="Revenue A"
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

        self.valid_data = {
            "sys_code": "SYS001",
            "bill_dept": "Finance",
            "description": "Monthly subscription",
            "revenue_source": 1,
            "customer": self.valid_customer_data,
        }

    def test_bill_creation_success(self):
        serializer = BillSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        bill = serializer.save()

        self.assertIsInstance(bill, Bill)
        self.assertEqual(bill.sys_info, self.system_info)
        self.assertEqual(bill.dept, self.billing_dept)
        self.assertEqual(bill.customer.email, "john.smith@example.com")

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
        self.assertFalse(serializer.is_valid())
        self.assertIn("sys_code", serializer.errors)

    def test_nonexistent_bill_dept(self):
        invalid_data = self.valid_data.copy()
        invalid_data["bill_dept"] = "INVALID_DEPT"

        serializer = BillSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bill_dept", serializer.errors)

    def test_nonexistent_revenue_source(self):
        invalid_data = self.valid_data.copy()
        invalid_data["revenue_source"] = 9999

        serializer = BillSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("revenue_source", serializer.errors)

    def test_update_not_supported(self):
        bill = Bill.objects.create(
            sys_info=self.system_info,
            dept=self.billing_dept,
            customer=Customer.objects.create(**self.valid_customer_data),
        )

        serializer = BillSerializer(instance=bill, data=self.valid_data)
        with self.assertRaises(ValidationError) as context:
            serializer.update(bill, self.valid_data)

        self.assertIn("Update operation not supported", str(context.exception))
