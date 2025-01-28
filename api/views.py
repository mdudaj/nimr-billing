import logging

from django.views.generic import View
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from billing.tasks import send_bill_control_number_request
from billing.utils import generate_request_id

from .models import BillCntrlNum, BillPayment
from .serializers import BillSerializer

logger = logging.getLogger(__name__)


class BillSubmissionView(viewsets.ModelViewSet):
    permission_classes = [HasAPIKey]
    serializer_class = BillSerializer

    def create(self, request):
        try:
            bill_data = request.data
            bill_serializer = BillSerializer(data=bill_data)

            logger.info(f"Received bill data: {bill_data}")

            if bill_serializer.is_valid():
                bill = bill_serializer.save()

                logger.info(
                    f"Bill saved successfully: {bill.bill_id} - {bill_serializer.validated_data}"
                )

                # Generate request id
                req_id = generate_request_id()

                # Schedule task to send bill control number request
                send_bill_control_number_request.delay(req_id, bill.bill_id)

                response_data = {
                    "req_id": req_id,
                    "bill_id": bill.bill_id,
                    "amount": bill.amt,
                    "currency": bill.currency,
                    "message": "Bill submitted successfully",
                }

                return Response(response_data, status=status.HTTP_201_CREATED)

            return Response(bill_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillCntrNumResponseCallback(View):
    def post(self, request):
        try:
            req_id = request.POST.get("req_id")
            bill_id = request.POST.get("bill_id")
            cntrl_num = request.POST.get("cntrl_num")
            bill_amt = request.POST.get("bill_amt")

            BillCntrlNum.objects.create(
                req_id=req_id,
                bill_id=bill_id,
                cntrl_num=cntrl_num,
                bill_amt=bill_amt,
            )

            return Response(
                {"message": "Bill control number response received"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillCntrNumPaymentCallback(View):
    def post(self, request):
        try:
            bill_id = request.POST.get("bill_id")
            psp_code = request.POST.get("psp_code")
            psp_name = request.POST.get("psp_name")
            trx_id = request.POST.get("trx_id")
            payref_id = request.POST.get("payref_id")
            bill_amt = request.POST.get("bill_amt")
            paid_amt = request.POST.get("paid_amt")
            paid_ccy = request.POST.get("paid_ccy")
            coll_acc_num = request.POST.get("coll_acc_num")
            trx_date = request.POST.get("trx_date")
            pay_channel = request.POST.get("pay_channel")
            pay_cell_num = request.POST.get("pay_cell_num")

            BillPayment.objects.create(
                bill_id=bill_id,
                psp_code=psp_code,
                psp_name=psp_name,
                trx_id=trx_id,
                payref_id=payref_id,
                bill_amt=bill_amt,
                paid_amt=paid_amt,
                paid_ccy=paid_ccy,
                coll_acc_num=coll_acc_num,
                trx_date=trx_date,
                pay_channel=pay_channel,
                pay_cell_num=pay_cell_num,
            )

            return Response(
                {"message": "Bill payment response received"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
