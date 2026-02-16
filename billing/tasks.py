import uuid
from datetime import datetime, timedelta

import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.db import IntegrityError, models
from django.http import JsonResponse
from django.utils import timezone

from .models import (
    Bill,
    BillingEmailDelivery,
    CancelledBill,
    Currency,
    ExchangeRate,
    Payment,
    PaymentGatewayLog,
    ReconciliationRun,
    PaymentReconciliation,
    SystemInfo,
)
from .utils import (
    compose_acknowledgement_response_payload,
    compose_bill_control_number_request_payload,
    compose_bill_reconciliation_request_payload,
    compose_bill_reconciliation_response_acknowledgement_payload,
    generate_invoice_pdf_bytes,
    generate_receipt_pdf_bytes,
    get_exchange_rate,
    load_private_key,
    parse_bill_control_number_request_acknowledgement,
    parse_bill_control_number_response,
    parse_bill_reconciliation_request_acknowledgement,
    parse_bill_reconciliation_response,
    parse_payment_response,
    select_billing_email_recipients,
    xml_to_dict,
)

logger = get_task_logger(__name__)

def _enqueue_bill_document_deliveries(*, bill, document_type, event_key, payer_email=None):
    """Create (idempotent) BillingEmailDelivery rows and enqueue Celery send task."""

    recipients, suppression_reason = select_billing_email_recipients(
        bill, payer_email=payer_email
    )

    if not recipients:
        BillingEmailDelivery.objects.get_or_create(
            bill=bill,
            document_type=document_type,
            recipient_email=(getattr(getattr(bill, "customer", None), "email", "") or "").strip(),
            event_key=event_key,
            defaults={
                "status": "NOT_SENT",
                "enqueued_at": timezone.now(),
                "failure_reason": suppression_reason or "no_recipient_email",
            },
        )
        return

    for email in recipients:
        delivery, created = BillingEmailDelivery.objects.get_or_create(
            bill=bill,
            document_type=document_type,
            recipient_email=email,
            event_key=event_key,
            defaults={"status": "PENDING", "enqueued_at": timezone.now()},
        )
        if created:
            send_bill_document_email.delay(delivery.id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_bill_document_email(self, delivery_id):
    """Send a single invoice/receipt email for a BillingEmailDelivery record."""

    try:
        delivery = BillingEmailDelivery.objects.select_related("bill").get(
            id=delivery_id
        )
    except BillingEmailDelivery.DoesNotExist:
        logger.warning("Delivery record not found", extra={"delivery_id": delivery_id})
        return

    if delivery.status == "SENT":
        return
    if delivery.status == "NOT_SENT":
        return

    now = timezone.now()
    BillingEmailDelivery.objects.filter(id=delivery.id).update(
        attempt_count=delivery.attempt_count + 1,
        last_attempt_at=now,
        failure_reason=None,
    )

    bill = delivery.bill
    subject = f"{delivery.document_type.title()} for Bill {bill.bill_id}"  # refined later (T016/T021)
    body = f"Please find your {delivery.document_type.lower()} attached for bill {bill.bill_id}."

    attachment_name = None
    attachment_bytes = None

    if delivery.document_type == "INVOICE":
        if not bill.cntr_num:
            BillingEmailDelivery.objects.filter(id=delivery.id).update(
                status="FAILED",
                failure_reason="missing_control_number",
            )
            return
        attachment_name = f"{bill.bill_id}_NatHREC.pdf"
        attachment_bytes = generate_invoice_pdf_bytes(bill)
    elif delivery.document_type == "RECEIPT":
        try:
            payment = Payment.objects.get(bill=bill)
        except Payment.DoesNotExist:
            BillingEmailDelivery.objects.filter(id=delivery.id).update(
                status="FAILED",
                failure_reason="missing_payment",
            )
            return
        attachment_name = f"{bill.bill_id}_Receipt_NatHREC.pdf"
        attachment_bytes = generate_receipt_pdf_bytes(payment)
    else:
        BillingEmailDelivery.objects.filter(id=delivery.id).update(
            status="FAILED",
            failure_reason="unknown_document_type",
        )
        return

    from_email = (
        f"{settings.BILLING_EMAIL_SENDER_NAME} <{settings.BILLING_EMAIL_FROM_EMAIL}>"
    )
    email_obj = EmailMessage(subject, body, from_email, [delivery.recipient_email])
    email_obj.attach(attachment_name, attachment_bytes, "application/pdf")

    try:
        email_obj.send(fail_silently=False)
    except Exception as exc:
        BillingEmailDelivery.objects.filter(id=delivery.id).update(
            status="FAILED",
            failure_reason=str(exc),
        )
        raise self.retry(exc=exc)

    BillingEmailDelivery.objects.filter(id=delivery.id).update(
        status="SENT",
        sent_at=timezone.now(),
        failure_reason=None,
    )


@shared_task
def send_mail_notification(email, subject, message, attachment=None):
    # Create an EmailMessage object
    email_obj = EmailMessage(subject, message, settings.EMAIL_HOST_USER, [email])

    # Attach a file if provided
    if attachment:
        email_obj.attach_file(attachment)

    # Send the email
    email_obj.send()


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retry 5 times with an initial delay of 60 seconds
def send_bill_control_number_request(self, req_id, bill_id):
    try:
        # Fetch the Bill object using the bill_id
        bill = Bill.objects.get(bill_id=bill_id)

        # Send the bill control number request to the Payment Gateway API
        url = settings.BILL_SUBMISSION_URL

        # GEPG API headers
        headers = {
            "Content-Type": "application/xml",
            "Gepg-Com": settings.GEPG_COM,
            "Gepg-Code": settings.GEPG_CODE,
            "Gepg-Alg": settings.GEPG_ALG,
        }

        # Load the private key for signing the request
        private_key = load_private_key(
            settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
        )

        # Compose the bill control number request payload
        payload = compose_bill_control_number_request_payload(
            req_id,
            bill,
            settings.SP_GRP_CODE,
            settings.SP_CODE,
            settings.SUB_SP_CODE,
            settings.SP_SYS_ID,
            private_key,
        )

        # Create a PaymentGatewayLog object to store the request and response data
        pg_log, created = PaymentGatewayLog.objects.get_or_create(
            bill=bill,
            req_id=req_id,
            req_type="1",
            defaults={"req_data": xml_to_dict(payload)},
        )

        if not created:
            logger.info(
                f"PaymentGatewayLog entry for req_id: {req_id}, req_type: '1' already exists. Skipping creation."
            )

        # Send the bill control number request to the GEPG API
        logger.info(f"Sending bill control number request: {payload}")
        response = requests.post(url, headers=headers, data=payload)

        # Update the PaymentGatewayLog object with the response data
        pg_log.req_ack = xml_to_dict(response.text)
        pg_log.save()
        logger.info(
            f"Bill control number request sent: Status - {response.status_code}, Response - {response.text}"
        )

        # If response status is not successful, raise an exception to trigger retry
        response.raise_for_status()

        # Process the initial acknowledgement
        process_bill_control_number_request_acknowledgement.delay(response.text)

    except requests.RequestException as e:
        # Handle any request exceptions that occur during the request
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
            status="ERROR",
            status_desc=f"Error sending bill control number request: {str(e)}",
        )
        # Log the error
        logger.error(f"Error sending bill control number request: {e}")

        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
        # Handle any exceptions that occur during the request or processing of the response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
            status="ERROR",
            status_desc=f"Error sending bill control number request: {str(e)}",
        )
        # Log the error
        logger.error(f"Unexpected error sending bill control number request: {e}")
        # Send email notification to administrators
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error sending bill control number request for request ID: {req_id}, bill ID: {bill_id} - {str(e)}",
        )


@shared_task
def process_bill_control_number_request_acknowledgement(response_data):
    # Process the initial acknowledgement response
    # Access req_id to associate the task with the specific bill control number request
    # Check if acknowledgment indicates success or failure
    # If successful, proceed to fetch the final response
    # Otherwise, handle the failure scenario

    try:
        # Parse the initial acknowledgement response
        ack_id, req_id, ack_sts_code, ack_sts_desc = (
            parse_bill_control_number_request_acknowledgement(response_data)
        )

        if ack_sts_code == "7101":  # Successfull acknowledgement
            # Wait for GEPG API to process the request and send the final response
            # Log the status, the response will be processed by a callback

            # Update the PaymentGatewayLog object with the acknowledgment status and description
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
                status="PENDING",
                status_desc=f"Bill control number request acknowledged: {ack_sts_desc}",
            )
            # Log the successful acknowledgment
            logger.info(
                f"Bill control number request for the request ID: {req_id} was successful. Acknowledgement ID: {ack_id}"
            )
        else:
            # Any other acknowledgement status code, log and send send an email notification to administrators
            # Update the PaymentGatewayLog object with the status and description
            PaymentGatewayLog.objects.filter(req_id=req_id).update(
                status="ERROR",
                status_desc=f"Bill control number request acknowledged: {ack_sts_desc}",
            )
            logger.error(
                f"Error processing bill control number request for request ID: {req_id} - {ack_sts_desc}"
            )

            # Send email notification to developers
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing bill control number request : {req_id} - {ack_sts_desc}",
            )
    except Exception as e:
        # Handle any exceptions that occur during the processing of the acknowledgement response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
            status="ERROR",
            status_desc=f"Error processing acknowledgement response: {str(e)}",
        )
        # Log the error
        logger.error(f"Error processing acknowledgement response : {str(e)}")
        # Send email notification to administrators
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing acknowledgement response: {str(e)}",
        )


@shared_task
def process_bill_control_number_response(
    res_id,
    req_id,
    bill_id,
    cust_cntr_num,
    res_sts_code,
    res_sts_desc,
    bill_sts_code,
    bill_sts_desc,
):
    # Process the final response received from the GEPG API
    # Extract control number from the response and save it to the bill object
    # Handle success/failure scenarios accordingly

    try:
        # Process the final response based on the status code
        if res_sts_code == "7101":  # Successful response
            logger.info(
                f"Bill {bill_id} control number request {req_id} processed successfully. Control Number: {cust_cntr_num}"
            )
            # Update the bill object with the control number
            bill = Bill.objects.get(bill_id=bill_id)
            bill.cntr_num = cust_cntr_num
            bill.save()

            # Auto-send invoice to customer (idempotent by event_key).
            _enqueue_bill_document_deliveries(
                bill=bill,
                document_type="INVOICE",
                event_key=f"auto:invoice_cn:{cust_cntr_num}",
            )

            # Log the successful response
            # Update the PaymentGatewayLog object with success status and description
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
                status="SUCCESS",
                status_desc=f"Bill control number request processed successfully. Control Number: {cust_cntr_num}",
            )

            # Check if bill control number request came from external system
            if bill.sys_info is not None:
                # Send control number to the external system
                url = bill.sys_info.cntrnum_response_callback
                headers = {"Content-Type": "application/json"}
                payload = {
                    "req_id": req_id,
                    "bill_id": bill_id,
                    "cntr_num": cust_cntr_num,
                    "bill_print_url": f"{settings.PUBLIC_URL}{bill.get_transfer_print_url()}",
                }
                response = requests.post(
                    url, headers=headers, json=payload, verify=False
                )

                # Update the PaymentGatewayLog object with the response data
                if response.status_code == 200:
                    PaymentGatewayLog.objects.filter(
                        req_id=req_id, req_type="1"
                    ).update(
                        status="SUCCESS",
                        status_desc=f"Control number {cust_cntr_num} sent to {bill.sys_info.name}",
                    )
                else:
                    PaymentGatewayLog.objects.filter(
                        req_id=req_id, req_type="1"
                    ).update(
                        status="ERROR",
                        status_desc=f"Error sending control number {cust_cntr_num} to {bill.sys_info.name}",
                    )

        else:
            # Any other response status code log and send an email notification to developers
            # Update the PaymentGatewayLog object with status and description
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
                status="ERROR",
                status_desc=f"Error processing control number request final response: {bill_sts_desc}",
            )
            # Log the error
            logger.error(
                f"Error processing final response: {bill_sts_code}: {bill_sts_desc}"
            )
            # Send email notification to administrators
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing final response for bill ID: {bill_id} - {bill_sts_code}: {bill_sts_desc}",
            )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the final response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="1").update(
            status="ERROR",
            status_desc=f"Error processing final response: {str(e)}",
        )
        # Log the error
        logger.error(
            f"Error processing final response for the request - {req_id} and  Bill ID - {bill_id}: {str(e)}"
        )
        # Send email notification to administrators
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing final response for the request - {req_id} and  Bill ID - {bill_id}: {str(e)}",
        )


@shared_task
def process_bill_payment_response(
    req_id,
    bill_id,
    cust_cntr_num,
    psp_code,
    psp_name,
    trx_id,
    payref_id,
    bill_amt,
    paid_amt,
    paid_ccy,
    coll_acc_num,
    trx_date,
    pay_channel,
    trdpty_trx_id,
    pyr_cell_num,
    pyr_email,
    pyr_name,
):
    # Process the payment response received from the GEPG API
    # Extract relevant information from the response and update payment object

    try:
        bill = Bill.objects.get(bill_id=bill_id)

        # Convert trx_date to an ISO 8601 string
        trx_date_str = (
            trx_date.isoformat() if isinstance(trx_date, datetime) else trx_date
        )

        # Check if the payment information with the same control number has already been processed to avoid reposting
        if Payment.objects.filter(bill=bill, cust_cntr_num=cust_cntr_num).exists():
            logger.warning(
                f"Duplicate payment detected for control number: {cust_cntr_num}. Skipping processing..."
            )
            return

        # Create a Payment object to store the payment response details
        payment = Payment.objects.create(
            bill=bill,
            cust_cntr_num=cust_cntr_num,
            psp_code=psp_code,
            psp_name=psp_name,
            trx_id=trx_id,
            payref_id=payref_id,
            bill_amt=bill_amt,
            paid_amt=paid_amt,
            currency=paid_ccy,
            coll_acc_num=coll_acc_num,
            trx_date=trx_date,
            pay_channel=pay_channel,
            trdpty_trx_id=trdpty_trx_id,
            pyr_cell_num=pyr_cell_num,
            pyr_email=pyr_email,
            pyr_name=pyr_name,
        )

        # Check if bill control number request came from external system
        if bill.sys_info is not None:
            # Send payment response to the external system
            url = bill.sys_info.pay_notification_callback
            headers = {"Content-Type": "application/json"}
            payload = {
                "bill_id": bill_id,
                "cntr_num": cust_cntr_num,
                "psp_code": psp_code,
                "psp_name": psp_name,
                "trx_id": trx_id,
                "payref_id": payref_id,
                "bill_amt": bill_amt,
                "paid_amt": paid_amt,
                "paid_ccy": paid_ccy,
                "coll_acc_num": coll_acc_num,
                "trx_date": trx_date_str,
                "pay_channel": pay_channel,
                "pyr_cell_num": pyr_cell_num,
                "bill_receipt_url": f"{settings.PUBLIC_URL}{bill.get_receipt_print_url()}",
            }
            response = requests.post(url, headers=headers, json=payload, verify=False)

            # Update the PaymentGatewayLog object with the response data
            if response.status_code == 200:
                # Update the payment gateway log with the response data
                PaymentGatewayLog.objects.filter(req_id=req_id, req_type="5").update(
                    status="SUCCESS",
                    status_desc=f"Payment notification sent to {bill.sys_info.name}",
                    res_data=response.json(),
                )
            else:
                # Update the payement gateway log with the response data
                PaymentGatewayLog.objects.filter(req_id=req_id, req_type="5").update(
                    status="ERROR",
                    status_desc=f"Error sending payment notification to {bill.sys_info.name}",
                    res_data=response.json(),
                )

        # Log the successful payment response
        logger.info(
            f"Payment response for request ID: {req_id} and Bill ID: {bill_id} processed successfully."
        )

        # Auto-send receipt (idempotent by event_key).
        _enqueue_bill_document_deliveries(
            bill=bill,
            document_type="RECEIPT",
            event_key=f"auto:receipt_payref:{payref_id}",
            payer_email=pyr_email,
        )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the payment response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="5").update(
            status="ERROR",
            status_desc=f"Error processing payment response: {str(e)}",
        )
        # Log the error
        logger.error(
            f"Error processing payment response for request ID: {req_id} and Bill ID: {bill_id}: {str(e)}"
        )
        # Send email notification to administrators
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing payment response: {str(e)}",
        )


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retry 5 times with an initial delay of 60 seconds
def send_bill_reconciliation_request(self, req_id, sp_grp_code, sys_code, trxDt):
    # Send the bill reconciliation request to the GEPG API
    # This task is triggered by a scheduled task for reconciliation of the previous day starting between 0600hrs to 2359hrs

    # Record the run early for audit/idempotency (even if the HTTP request fails).
    try:
        trx_date = datetime.strptime(trxDt, "%Y-%m-%d").date()
    except ValueError:
        trx_date = None

    ReconciliationRun.objects.update_or_create(
        req_id=req_id,
        defaults={
            "trx_date": trx_date or timezone.localdate(),
            "status": "REQUESTED",
            "requested_at": timezone.now(),
        },
    )

    # Load private key for signing the request
    private_key = load_private_key(
        settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
    )

    try:
        # Send the bill reconciliation request to the Payment Gateway API
        url = settings.RECONCILIATION_REQUEST_URL

        # GEPG API headers
        headers = {
            "Content-Type": "application/xml",
            "Gepg-Com": settings.GEPG_COM,
            "Gepg-Code": settings.GEPG_CODE,
            "Gepg-Alg": settings.GEPG_ALG,
        }

        # Compose the bill reconciliation request payload
        payload = compose_bill_reconciliation_request_payload(
            req_id, sp_grp_code, sys_code, trxDt, private_key
        )

        # Create a PaymentGatewayLog object to store the request data
        pg_log = PaymentGatewayLog.objects.create(
            req_id=req_id,
            req_type="6",
            req_data=xml_to_dict(payload),
        )

        logger.info(
            f"Sending reconciliation request Request ID: {req_id} Payload: {payload}"
        )

        # Send the bill reconciliation request to the GEPG API
        response = requests.post(url, headers=headers, data=payload)

        logger.info(
            f"Reconciliation request sent: Status code {response.status_code} - Response {response.text}"
        )

        # Update the PaymentGatewayLog object with the acknowledgment response data
        pg_log.req_ack = xml_to_dict(response.text)
        pg_log.save()

        # If response status is not successful, raise an exception to trigger retry
        response.raise_for_status()

        # Process the bill reconciliation request acknowledgement
        process_bill_reconciliation_request_acknowledgement.delay(response.text)

    except requests.RequestException as e:
        # Handle any request exceptions that occur during the request
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="ERROR",
            status_desc=f"Error sending bill reconciliation request: {str(e)}",
        )
        # Log the error
        logger.error(f"Error sending bill reconciliation request: {e}")

        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
        # Handle any other exceptions that occur during the request
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="ERROR",
            status_desc=f"Error sending bill reconciliation request: {str(e)}",
        )
        # Log the error
        logger.error(f"Unexpected error sending bill reconciliation request: {e}")

        # Send email notification
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error sending bill reconciliation request - {str(e)}",
        )


@shared_task
def process_bill_reconciliation_request_acknowledgement(response_data):
    # Process the bill reconciliation request acknowledgement
    # Extract relevant information from the response and handle success/failure scenarios

    try:
        # Parse the bill reconciliation request acknowledgement response
        ack_id, req_id, ack_sts_code, ack_sts_desc = (
            parse_bill_reconciliation_request_acknowledgement(response_data)
        )

        if ack_sts_code == "7101":  # Successful acknowledgement
            # Log the successful acknowledgement
            logger.info(
                f"Bill reconciliation request for request ID: {req_id} was successful. Acknowledgement ID: {ack_id}"
            )

            # Update the PaymentGatewayLog object with the acknowledgment status and description
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
                status="PENDING",
                status_desc=ack_sts_desc,
            )
            ReconciliationRun.objects.filter(req_id=req_id).update(
                status="ACKED",
                acked_at=timezone.now(),
                last_error=None,
            )
        else:
            # Any other acknowledgement status code, log and send an email notification to developers
            logger.error(
                f"Error processing bill reconciliation request for request ID: {req_id} - {ack_sts_desc}"
            )
            # Update the PaymentGatewayLog status and description
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
                status="ERROR",
                status_desc=ack_sts_desc,
            )
            ReconciliationRun.objects.filter(req_id=req_id).update(
                status="ERROR",
                acked_at=timezone.now(),
                last_error=ack_sts_desc,
            )
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing bill reconciliation request - {ack_sts_desc}",
            )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the acknowledgement response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="ERROR",
            status_desc=f"Error processing bill reconciliation request acknowledgement: {str(e)}",
        )
        ReconciliationRun.objects.filter(req_id=req_id).update(
            status="ERROR",
            last_error=str(e),
        )
        logger.error(
            f"Error processing bill reconciliation request acknowledgement: {str(e)}"
        )
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing bill reconciliation request acknowledgement - {str(e)}",
        )


@shared_task
def process_bill_reconciliation_response(
    res_id, req_id, pay_sts_code, pay_sts_desc, pmt_trx_dtls
):
    # Process the bill reconciliation response received from the GEPG API
    try:
        existing_run = ReconciliationRun.objects.filter(req_id=req_id).first()
        if existing_run and existing_run.status == "CLOSED":
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
                status="SUCCESS",
                status_desc="Reconciliation response received after close; no changes applied.",
            )
            logger.warning(
                "Reconciliation response received after close for req_id=%s res_id=%s",
                req_id,
                res_id,
            )
            return

        run, _ = ReconciliationRun.objects.update_or_create(
            req_id=req_id,
            defaults={
                "res_id": res_id,
                "pay_sts_code": pay_sts_code,
                "pay_sts_desc": pay_sts_desc,
                "status": "RECEIVED",
                "received_at": timezone.now(),
                "last_error": None,
            },
        )

        processed = 0

        def _match_and_flag(rec: PaymentReconciliation):
            mismatch_reasons = []

            bill = Bill.objects.filter(bill_id=rec.bill_id).first()
            if not bill:
                rec.match_status = "BILL_NOT_FOUND"
                rec.mismatch_reason = "bill_not_found"
                rec.bill_ref = None
                rec.payment = None
                rec.save(
                    update_fields=[
                        "match_status",
                        "mismatch_reason",
                        "bill_ref",
                        "payment",
                        "updated_at",
                    ]
                )
                return

            rec.bill_ref = bill

            payment = Payment.objects.filter(bill=bill).first()
            rec.payment = payment

            if not payment:
                rec.match_status = "MISSING_INTERNAL_PAYMENT"
                rec.mismatch_reason = None
                rec.save(
                    update_fields=[
                        "match_status",
                        "mismatch_reason",
                        "bill_ref",
                        "payment",
                        "updated_at",
                    ]
                )
                return

            # Basic accuracy checks
            if payment.currency != rec.currency:
                mismatch_reasons.append("currency_mismatch")
            if payment.paid_amt != rec.paid_amt:
                mismatch_reasons.append("paid_amount_mismatch")
            if payment.bill_amt != rec.bill_amt:
                mismatch_reasons.append("bill_amount_mismatch")
            try:
                if bill.cntr_num and rec.bill_ctr_num and int(bill.cntr_num) != int(
                    rec.bill_ctr_num
                ):
                    mismatch_reasons.append("control_number_mismatch")
            except (TypeError, ValueError):
                mismatch_reasons.append("control_number_format_error")

            if mismatch_reasons:
                rec.match_status = "MISMATCH"
                rec.mismatch_reason = ",".join(mismatch_reasons)
            else:
                rec.match_status = "MATCHED"
                rec.mismatch_reason = None

            rec.save(
                update_fields=[
                    "match_status",
                    "mismatch_reason",
                    "bill_ref",
                    "payment",
                    "updated_at",
                ]
            )

        # Check if payment transaction details are available and upsert records idempotently.
        if pmt_trx_dtls:
            for pmt_trx_dtl in pmt_trx_dtls:
                pmt_trx_dtl["reconciliation_run"] = run
                rec, _created = PaymentReconciliation.objects.update_or_create(
                    payref_id=pmt_trx_dtl["payref_id"],
                    defaults=pmt_trx_dtl,
                )
                _match_and_flag(rec)
                processed += 1

        # Control totals
        totals = {}
        for row in PaymentReconciliation.objects.filter(reconciliation_run=run).values(
            "currency"
        ).annotate(total=models.Sum("paid_amt"), count=models.Count("id")):
            totals[row["currency"]] = {
                "total_paid": str(row["total"] or 0),
                "count": row["count"],
            }

        internal_totals = {}
        for row in (
            PaymentReconciliation.objects.filter(
                reconciliation_run=run, payment__isnull=False
            )
            .values("currency")
            .annotate(
                total=models.Sum("payment__paid_amt"),
                count=models.Count("payment", distinct=True),
            )
        ):
            internal_totals[row["currency"]] = {
                "total_paid": str(row["total"] or 0),
                "count": row["count"],
            }

        run.record_count = PaymentReconciliation.objects.filter(
            reconciliation_run=run
        ).count()
        run.totals_by_currency = totals
        run.internal_totals_by_currency = internal_totals
        run.totals_match = totals == internal_totals
        run.status = "PROCESSED"
        run.processed_at = timezone.now()
        run.save(
            update_fields=[
                "record_count",
                "totals_by_currency",
                "internal_totals_by_currency",
                "totals_match",
                "status",
                "processed_at",
                "updated_at",
            ]
        )

        # Update the PaymentGatewayLog object with status and description (once).
        desc = (
            f"Bill reconciliation processed. {processed} record(s) received."
            if processed
            else "Bill reconciliation processed. No payment transactions received."
        )
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="SUCCESS",
            status_desc=desc,
        )

        # Queue auto-creation of missing Payment rows (controlled job).
        create_missing_payments_for_run.delay(run.id)

    except Exception as e:
        # Handle any exceptions that occur during the processing of the response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="ERROR",
            status_desc=f"Error processing bill reconciliation response: {str(e)}",
        )
        ReconciliationRun.objects.filter(req_id=req_id).update(
            status="ERROR",
            last_error=str(e),
        )
        logger.error(
            f"Error processing bill reconciliation response for request ID: {req_id} - {str(e)}"
        )
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing bill reconciliation response for request ID: {req_id} - {str(e)}",
        )


@shared_task
def create_missing_payments_for_run(run_id: int):
    """Create internal Payment records for reconciliation rows missing an internal Payment (async, controlled)."""
    try:
        run = ReconciliationRun.objects.get(id=run_id)
    except ReconciliationRun.DoesNotExist:
        return

    if run.status == "CLOSED":
        return

    qs = PaymentReconciliation.objects.select_related("bill_ref").filter(
        reconciliation_run=run,
        match_status="MISSING_INTERNAL_PAYMENT",
        bill_ref__isnull=False,
    )

    for rec in qs:
        if ReconciliationRun.objects.filter(id=run.id, status="CLOSED").exists():
            return

        bill = rec.bill_ref
        try:
            payment, created = Payment.objects.get_or_create(
                bill=bill,
                defaults={
                    "cust_cntr_num": rec.cust_cntr_num,
                    "psp_code": rec.psp_code,
                    "psp_name": rec.psp_name,
                    "trx_id": rec.trx_id,
                    "payref_id": rec.payref_id,
                    "bill_amt": rec.bill_amt,
                    "paid_amt": rec.paid_amt,
                    "currency": rec.currency,
                    "coll_acc_num": rec.coll_acc_num,
                    "trx_date": rec.trx_date,
                    "pay_channel": rec.usd_pay_chnl,
                    "trdpty_trx_id": rec.trdpty_trx_id,
                    "pyr_cell_num": rec.pyr_cell_num,
                    "pyr_email": rec.pyr_email,
                    "pyr_name": rec.pyr_name,
                },
            )
        except IntegrityError:
            payment = Payment.objects.filter(bill=bill).first()
            if not payment:
                raise
            created = False

        rec.payment = payment
        if created:
            rec.match_status = "AUTO_CREATED"
            rec.mismatch_reason = None
        else:
            mismatch_reasons = []
            if payment.currency != rec.currency:
                mismatch_reasons.append("currency_mismatch")
            if payment.paid_amt != rec.paid_amt:
                mismatch_reasons.append("paid_amount_mismatch")
            if payment.bill_amt != rec.bill_amt:
                mismatch_reasons.append("bill_amount_mismatch")
            try:
                if bill.cntr_num and rec.bill_ctr_num and int(bill.cntr_num) != int(
                    rec.bill_ctr_num
                ):
                    mismatch_reasons.append("control_number_mismatch")
            except (TypeError, ValueError):
                mismatch_reasons.append("control_number_format_error")

            if mismatch_reasons:
                rec.match_status = "MISMATCH"
                rec.mismatch_reason = ",".join(mismatch_reasons)
            else:
                rec.match_status = "MATCHED"
                rec.mismatch_reason = None

        rec.save(
            update_fields=["payment", "match_status", "mismatch_reason", "updated_at"]
        )


@shared_task
def request_daily_reconciliation(backfill_days: int = 7):
    """Trigger GePG reconciliation requests for the previous business date + bounded backfill (<= 7 days)."""
    # GePG expects reconciliation requests for the previous day between 06:00-23:59.
    target = timezone.localdate() - timedelta(days=1)
    days = max(1, min(int(backfill_days or 1), 7))

    for offset in range(days):
        trx_date = target - timedelta(days=offset)
        if ReconciliationRun.objects.filter(trx_date=trx_date).exclude(status="ERROR").exists():
            continue
        req_id = str(uuid.uuid4())
        send_bill_reconciliation_request.delay(
            req_id, settings.SP_GRP_CODE, settings.SP_SYS_ID, trx_date.isoformat()
        )


@shared_task
def update_exchange_rates(url: str, trx_date: str = None):
    """
    Fetches the latest exchange rates from the specified URL and updates the database if does not exist.

    Args:
        url (str): The URL to fetch the exchange rates from.
        trx_date (str): The date of the exchange rate. Defaults to None.
    """
    if not trx_date:
        trx_date = timezone.now().date().strftime("%d-%b-%y")

    # Check if the exchange rate for the current date already exists
    if ExchangeRate.objects.filter(trx_date=timezone.now().date()).exists():
        logger.warning(f"Exchange rates for {trx_date} already exist. Skipping update.")
        return

    active_currencies = Currency.objects.filter(is_active=True)

    for currency in active_currencies:
        try:
            result = get_exchange_rate(url, currency.code)
            if result:
                buying, selling, transaction_date = result

                # Ensure transaction date is the same as the one provided
                if transaction_date != trx_date:
                    logger.warning(
                        f"Transaction date {transaction_date} does not match the provided date {trx_date}. Skipping update."
                    )
                    continue

                # Update or create the exchange rate entry
                _, created = ExchangeRate.objects.get_or_create(
                    currency=currency,
                    trx_date=datetime.strptime(transaction_date, "%d-%b-%y"),
                    defaults={
                        "buying": buying,
                        "selling": selling,
                    },
                )
                action = "Created" if created else "Updated"
                logger.info(
                    f"{action} exchange rate for {currency.code} on {transaction_date}"
                )

            else:
                logger.warning(
                    f"Exchange rate for {currency.code} on {trx_date} not found."
                )

        except IntegrityError as e:
            logger.error(
                f"Integrity error updating exchange rate for {currency.code}: {e}"
            )

        except Exception as e:
            logger.error(f"Error fetching exchange rate for {currency.code}: {e}")
