from rest_framework import serializers
from billing.models import (
    Bill,
    BillItem,
    # BillingDepartment,
    Customer,
    RevenueSourceItem,
)


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "cell_num",
            "email",
        ]
        read_only_fields = ["id"]


class ReveneSourceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevenueSourceItem
        fields = [
            "id",
        ]


class BillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillItem
        fields = [
            "rev_src_itm",
        ]


class BillSerializer(serializers.ModelSerializer):
    sys_code = serializers.CharField(max_length=50, required=True)
    customer = CustomerSerializer()
    item = BillItemSerializer()

    class Meta:
        model = Bill
        fields = [
            "sys_code",
            "description",
            "customer",
            "item",
        ]
