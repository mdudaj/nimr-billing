import logging
import re
from rest_framework import serializers
from billing.models import (
    Bill,
    BillItem,
    BillingDepartment,
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

    class Meta:
        model = Bill
        fields = [
            "sys_code",
            "bill_dept",
            "description",
            "revenue_source",
            "customer",
        ]

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

        if not serializers.EmailField().to_internal_value(email):
            raise serializers.ValidationError("Invalid email address")

        # Check if the cell number is valid
        cell_num = value.get("cell_num")

        if not re.fullmatch(r"^\d{12}$", cell_num):
            raise serializers.ValidationError(
                "Cell number must have exactly twelve digits including the country code (e.g., 255XXXXXXXXX)"
            )

        return value

    def create(self, validated_data):
        try:
            sys_code_data = validated_data.pop("sys_code")
            bill_dept_data = validated_data.pop("bill_dept")
            customer_data = validated_data.pop("customer")
            revenue_source_data = validated_data.pop("revenue_source")

            sys_info = SystemInfo.objects.get(code=sys_code_data)
            billing_dept = BillingDepartment.objects.get(name=bill_dept_data)

            customer, created = Customer.objects.get_or_create(
                email=customer_data.get("email"),
                defaults=customer_data,
            )

            # Create the bill object
            bill = Bill.objects.create(
                sys_info=sys_info,
                dept=billing_dept,
                customer=customer,
                gen_by=customer.get_name(),
                appr_by=customer.get_name(),
                **validated_data,
            )

            # Handle bill item
            rev_src_itm = RevenueSourceItem.objects.get(id=revenue_source_data)
            BillItem.objects.create(
                bill=bill,
                dept=billing_dept,
                rev_src_itm=rev_src_itm,
            )

            # Update the bill object with amount, equevalent amount, and max amount
            bill.currency = rev_src_itm.currency
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
