from rest_framework import viewsets, status
from rest_framework.response import Response
from billing.models import (
    Bill,
    BillItem,
    BillingDepartment,
    Customer,
    RevenueSourceItem,
    SystemInfo,
)
from billing.tasks import send_bill_control_number_request
from billing.utils import generate_request_id

from .serializers import BillSerializer, BillItemSerializer, CustomerSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all()
    serializer_class = BillSerializer

    def create(self, request):
        try:
            bill_data = request.data

            sys_code_data = bill_data.pop("sys_code")
            sys_info = SystemInfo.objects.get(code=sys_code_data)

            customer_data = bill_data.pop("customer")
            customer, created = Customer.objects.get_or_create(
                email=customer_data["email"], defaults=customer_data
            )
            if not created:
                CustomerSerializer(customer).update(customer, customer_data)

            billing_dept = BillingDepartment.objects.get(name="NIMR HQ")

            bill_data["sys_info"] = sys_info
            bill_data["dept"] = billing_dept
            bill_data["customer"] = customer
            bill_data["gen_by"] = customer.get_name()
            bill_data["appr_by"] = customer.get_name()
            bill_serializer = BillSerializer(data=bill_data)

            if bill_serializer.is_valid():
                bill = bill_serializer.save()

                item_data = bill_data.pop("item")
                rev_src_itm_data = item_data.pop("rev_src_itm")
                rev_src_itm = RevenueSourceItem.objects.get(id=rev_src_itm_data["id"])
                item_data["bill"] = bill
                item_data["dept"] = billing_dept
                item_data["rev_src_itm"] = rev_src_itm
                BillItem.objects.create(**item_data)

                # Generate request id
                req_id = generate_request_id()

                # Schedule task to send bill control number request
                send_bill_control_number_request.delay(req_id, bill.bill_id)

                return Response(
                    {"req_id": req_id, "bill_id": bill.bill_id},
                    status=status.HTTP_201_CREATED,
                )

            return Response(bill_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
