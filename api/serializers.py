import logging
import re

from rest_framework import serializers

from billing.models import (
    Bill,
    BillingDepartment,
    BillItem,
    Customer,
    RevenueSourceItem,
    SystemInfo,
)

logger = logging.getLogger(__name__)


class BillSerializer(serializers.ModelSerializer):
    sys_code = serializers.CharField(max_length=50, required=True)
    bill_dept = serializers.CharField(max_length=50, required=True)
    customer = serializers.DictField(required=True, child=serializers.CharField())
    revenue_source = serializers.IntegerField(required=True)
    currency = serializers.CharField(max_length=3, required=False, default=None)

    class Meta:
        model = Bill
        fields = [
            "sys_code",
            "bill_dept",
            "description",
            "revenue_source",
            "customer",
            "currency",
        ]

    #
    def validate_customer(self, value):
        # Ensure that only the expected fields are present
        expected_fields = [
            "first_name",
            "middle_name",
            "last_name",
            "cell_num",
            "email",
        ]

        for field in value.keys():
            if field not in expected_fields:
                raise serializers.ValidationError(
                    f"Invalid field '{field}' in customer data"
                )

        # Ensure that required fields are present
        required_fields = ["first_name", "last_name", "cell_num", "email"]

        for field in required_fields:
            if field not in value.keys():
                raise serializers.ValidationError(f"Field '{field}' is required")

        # Check if the email is valid
        email = value.get("email")
        try:
            serializers.EmailField().run_validation(email)
        except serializers.ValidationError:
            raise serializers.ValidationError("Invalid email address")

        # Check if the cell number is valid
        cell_num = value.get("cell_num")
        if not isinstance(cell_num, str) or not re.fullmatch(r"^\d{12}$", cell_num):
            raise serializers.ValidationError(
                "Cell number must have exactly twelve digits including the country code (e.g., 255XXXXXXXXX)"
            )

        return value

    # Validate currency
    def validate_currency(self, value):
        if value is not None and value not in ["TZS", "USD"]:
            raise serializers.ValidationError("Invalid currency")

        return value

    def create(self, validated_data):
        try:
            sys_code_data = validated_data.pop("sys_code")
            bill_dept_data = validated_data.pop("bill_dept")
            customer_data = validated_data.pop("customer")
            revenue_source_data = validated_data.pop("revenue_source")
            currency_data = validated_data.pop("currency", None)

            # Get the system info and billing department objects
            sys_info = SystemInfo.objects.get(code=sys_code_data)
            billing_dept = BillingDepartment.objects.get(name=bill_dept_data)

            # Get or create the customer object
            customer, created = Customer.objects.get_or_create(
                email=customer_data.get("email"),
                defaults=customer_data,
            )

            # Get revenue source item
            rev_src_itm = RevenueSourceItem.objects.get(id=revenue_source_data)

            if currency_data is None:
                currency_data = rev_src_itm.currency

            # Create the bill object
            bill = Bill.objects.create(
                sys_info=sys_info,
                dept=billing_dept,
                customer=customer,
                currency=currency_data,
                gen_by=customer.get_name(),
                appr_by=customer.get_name(),
                **validated_data,
            )

            # Handle bill item
            BillItem.objects.create(
                bill=bill,
                dept=billing_dept,
                rev_src_itm=rev_src_itm,
            )

            # Update the bill object with amount, equevalent amount, and max amount
            bill.amt = sum([item.amt for item in bill.billitem_set.all()])
            bill.eqv_amt = bill.amt
            bill.min_amt = bill.amt
            bill.max_amt = bill.amt
            bill.save()

            return bill

        except SystemInfo.DoesNotExist:
            raise serializers.ValidationError({"sys_code": "Invalid system code"})
        except BillingDepartment.DoesNotExist:
            raise serializers.ValidationError(
                {"bill_dept": "Invalid billing department"}
            )
        except RevenueSourceItem.DoesNotExist:
            raise serializers.ValidationError(
                {"revenue_source": "Invalid revenue source"}
            )
        except Exception as e:
            raise serializers.ValidationError({"error": str(e)})

    def update(self, instance, validated_data):
        raise serializers.ValidationError("Update operation not supported")
