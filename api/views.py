import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import View
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from billing.models import Bill as BillingBill
from billing.models import BillingEmailDelivery
from billing.tasks import send_bill_control_number_request, send_bill_document_email
from billing.utils import generate_request_id, select_billing_email_recipients

from .models import ApiIdempotencyRecord, BillCntrlNum, BillPayment
from .serializers import BillingEmailDeliverySerializer, BillSerializer

logger = logging.getLogger(__name__)


def _to_jsonable(value):
    """Best-effort conversion to JSON-serializable primitives for JSONField storage."""
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


class BillSubmissionView(viewsets.ModelViewSet):
    permission_classes = [HasAPIKey]
    serializer_class = BillSerializer

    def create(self, request):
        bill_data = request.data

        # Avoid logging full payloads (PII). Log minimal metadata.
        logger.info(
            "Received bill submission request",
            extra={"path": request.path, "method": request.method},
        )

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        api_key_hash = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()

        now = timezone.now()
        bucket_minutes = 10
        bucket_start = now.replace(
            minute=(now.minute // bucket_minutes) * bucket_minutes,
            second=0,
            microsecond=0,
        )

        try:
            body_json = json.dumps(
                bill_data, sort_keys=True, separators=(",", ":"), default=str
            )
        except TypeError:
            # Fallback for non-JSON-serializable bodies.
            body_json = (request.body or b"").decode("utf-8", errors="replace")

        body_hash = hashlib.sha256(
            (bucket_start.isoformat() + "|" + body_json).encode("utf-8")
        ).hexdigest()

        method = request.method.upper()
        path = request.path

        # Use the DB as a concurrency-safe dedupe lock.
        try:
            with transaction.atomic():
                idempo = ApiIdempotencyRecord.objects.create(
                    api_key_hash=api_key_hash,
                    method=method,
                    path=path,
                    bucket_start=bucket_start,
                    body_hash=body_hash,
                    status=ApiIdempotencyRecord.STATUS_IN_PROGRESS,
                )

                bill_serializer = BillSerializer(data=bill_data)
                if not bill_serializer.is_valid():
                    idempo.status = ApiIdempotencyRecord.STATUS_FAILED
                    idempo.response_status = status.HTTP_400_BAD_REQUEST
                    idempo.response_body = _to_jsonable(bill_serializer.errors)
                    idempo.save(
                        update_fields=[
                            "status",
                            "response_status",
                            "response_body",
                            "updated_at",
                        ]
                    )
                    return Response(
                        bill_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

                bill = bill_serializer.save()

                req_id = generate_request_id()

                response_data = {
                    "req_id": req_id,
                    "bill_id": bill.bill_id,
                    "amount": str(bill.amt) if bill.amt is not None else None,
                    "currency": bill.currency,
                    "message": "Bill submitted successfully",
                }

                idempo.status = ApiIdempotencyRecord.STATUS_SUCCEEDED
                idempo.response_status = status.HTTP_201_CREATED
                idempo.response_body = _to_jsonable(response_data)
                idempo.req_id = req_id
                idempo.bill_id = bill.bill_id
                idempo.save(
                    update_fields=[
                        "status",
                        "response_status",
                        "response_body",
                        "req_id",
                        "bill_id",
                        "updated_at",
                    ]
                )

                def _enqueue():
                    try:
                        send_bill_control_number_request.delay(req_id, bill.bill_id)
                    except Exception:
                        logger.exception(
                            "Failed to enqueue bill control number request",
                            extra={"req_id": req_id, "bill_id": bill.bill_id},
                        )

                transaction.on_commit(_enqueue)

                return Response(response_data, status=status.HTTP_201_CREATED)

        except IntegrityError:
            # Duplicate request within the time bucket.
            existing = ApiIdempotencyRecord.objects.filter(
                api_key_hash=api_key_hash,
                method=method,
                path=path,
                bucket_start=bucket_start,
                body_hash=body_hash,
            ).first()

            if existing and existing.status == ApiIdempotencyRecord.STATUS_SUCCEEDED:
                return Response(
                    existing.response_body,
                    status=existing.response_status or status.HTTP_201_CREATED,
                )

            if existing and existing.status == ApiIdempotencyRecord.STATUS_FAILED:
                return Response(
                    existing.response_body or {"message": "Request failed"},
                    status=existing.response_status or status.HTTP_400_BAD_REQUEST,
                )

            # In progress (or unexpected state). Keep client behavior compatible: safe retry.
            in_progress_body = {
                "message": "Request is being processed",
            }
            if existing and existing.req_id:
                in_progress_body["req_id"] = existing.req_id
            if existing and existing.bill_id:
                in_progress_body["bill_id"] = existing.bill_id
            return Response(in_progress_body, status=status.HTTP_202_ACCEPTED)

        except Exception:
            logger.exception("Unhandled error in bill submission")
            return Response(
                {"message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BillCntrNumResponseCallback(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        req_id = data.get("req_id")
        bill_id = data.get("bill_id")
        cntrl_num = data.get("cntrl_num")
        bill_amt_raw = data.get("bill_amt")

        missing = [
            k for k in ["req_id", "bill_id", "cntrl_num", "bill_amt"] if not data.get(k)
        ]
        if missing:
            return Response(
                {"message": "Missing required fields", "missing": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            bill_amt = Decimal(str(bill_amt_raw))
        except (InvalidOperation, TypeError):
            return Response(
                {"message": "Invalid bill_amt"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                obj, created = BillCntrlNum.objects.update_or_create(
                    req_id=req_id,
                    defaults={
                        "bill_id": bill_id,
                        "cntrl_num": cntrl_num,
                        "bill_amt": bill_amt,
                    },
                )

            # If a duplicate arrives, return 200 so the sender can stop retrying.
            return Response(
                {
                    "message": "Bill control number response received",
                    "duplicate": not created,
                },
                status=status.HTTP_200_OK,
            )
        except IntegrityError:
            # Uniqueness conflict on bill_id or cntrl_num; treat as duplicate/conflict.
            logger.warning(
                "Control number callback uniqueness conflict",
                extra={"req_id": req_id, "bill_id": bill_id, "cntrl_num": cntrl_num},
            )
            return Response(
                {"message": "Bill control number already recorded"},
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.exception("Unhandled error in control-number callback")
            return Response(
                {"message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BillCntrNumPaymentCallback(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data

        bill_id = data.get("bill_id")
        psp_code = data.get("psp_code")
        psp_name = data.get("psp_name")
        trx_id = data.get("trx_id")
        payref_id = data.get("payref_id")
        bill_amt_raw = data.get("bill_amt")
        paid_amt_raw = data.get("paid_amt")
        paid_ccy = data.get("paid_ccy")
        coll_acc_num = data.get("coll_acc_num")
        trx_date_raw = data.get("trx_date")
        pay_channel = data.get("pay_channel")
        pay_cell_num = data.get("pay_cell_num")

        required = [
            "bill_id",
            "psp_code",
            "psp_name",
            "trx_id",
            "payref_id",
            "bill_amt",
            "paid_amt",
            "paid_ccy",
            "coll_acc_num",
            "trx_date",
            "pay_channel",
            "pay_cell_num",
        ]
        missing = [k for k in required if not data.get(k)]
        if missing:
            return Response(
                {"message": "Missing required fields", "missing": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            bill_amt = Decimal(str(bill_amt_raw))
            paid_amt = Decimal(str(paid_amt_raw))
        except (InvalidOperation, TypeError):
            return Response(
                {"message": "Invalid amount field"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trx_dt = parse_datetime(str(trx_date_raw))
        if trx_dt is None:
            return Response(
                {"message": "Invalid trx_date (expected ISO-8601 datetime)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bill_cntrl_num = BillCntrlNum.objects.filter(bill_id=bill_id).first()

        try:
            with transaction.atomic():
                obj, created = BillPayment.objects.update_or_create(
                    trx_id=trx_id,
                    defaults={
                        "bill_id": bill_id,
                        "bill_cntrl_num": bill_cntrl_num,
                        "psp_code": psp_code,
                        "psp_name": psp_name,
                        "payref_id": payref_id,
                        "bill_amt": bill_amt,
                        "paid_amt": paid_amt,
                        "paid_ccy": paid_ccy,
                        "coll_acc_num": coll_acc_num,
                        "trx_date": trx_dt,
                        "pay_channel": pay_channel,
                        "pay_cell_num": pay_cell_num,
                    },
                )

            return Response(
                {"message": "Bill payment response received", "duplicate": not created},
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.exception("Unhandled error in payment callback")
            return Response(
                {"message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InternalBillDeliveriesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, bill_id):
        bill = BillingBill.objects.filter(bill_id=bill_id).first()
        if not bill:
            return Response(
                {"message": "Bill not found"}, status=status.HTTP_404_NOT_FOUND
            )

        deliveries = BillingEmailDelivery.objects.filter(bill=bill).order_by(
            "-created_at"
        )
        return Response(
            {
                "bill_id": bill.bill_id,
                "deliveries": BillingEmailDeliverySerializer(
                    deliveries, many=True
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class InternalBillDeliveriesResendView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, bill_id):
        bill = BillingBill.objects.filter(bill_id=bill_id).first()
        if not bill:
            return Response(
                {"message": "Bill not found"}, status=status.HTTP_404_NOT_FOUND
            )

        document_type = (request.data or {}).get("document_type")
        recipient_email = (request.data or {}).get("recipient_email")

        if document_type not in {"INVOICE", "RECEIPT"}:
            return Response(
                {"message": "Invalid document_type", "allowed": ["INVOICE", "RECEIPT"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine recipients
        if recipient_email:
            recipients = [str(recipient_email).strip()]
            suppression_reason = None
        else:
            payer_email = None
            try:
                payer_email = bill.payment.pyr_email
            except Exception:
                payer_email = None
            recipients, suppression_reason = select_billing_email_recipients(
                bill, payer_email=payer_email
            )

        event_key = f"manual:{uuid.uuid4()}"

        if not recipients:
            # Record a NOT_SENT attempt so staff can see why it didn't send.
            BillingEmailDelivery.objects.create(
                bill=bill,
                document_type=document_type,
                recipient_email=recipient_email or (bill.customer.email or ""),
                event_key=event_key,
                status="NOT_SENT",
                enqueued_at=timezone.now(),
                failure_reason=suppression_reason or "no_recipient_email",
            )
            return Response(
                {"status": "ACCEPTED", "event_key": event_key},
                status=status.HTTP_202_ACCEPTED,
            )

        for email in recipients:
            delivery = BillingEmailDelivery.objects.create(
                bill=bill,
                document_type=document_type,
                recipient_email=email,
                event_key=event_key,
                status="PENDING",
                enqueued_at=timezone.now(),
            )
            send_bill_document_email.delay(delivery.id)

        return Response(
            {"status": "ACCEPTED", "event_key": event_key},
            status=status.HTTP_202_ACCEPTED,
        )
