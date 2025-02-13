from datetime import datetime, timedelta

import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone

from .models import (
    Bill,
    CancelledBill,
    Currency,
    ExchangeRate,
    Payment,
    PaymentGatewayLog,
    PaymentReconciliation,
    SystemInfo,
)
from .utils import (
    compose_acknowledgement_response_payload,
    compose_bill_control_number_request_payload,
    compose_bill_reconciliation_request_payload,
    compose_bill_reconciliation_response_acknowledgement_payload,
    get_exchange_rate,
    load_private_key,
    parse_bill_control_number_request_acknowledgement,
    parse_bill_control_number_response,
    parse_bill_reconciliation_request_acknowledgement,
    parse_bill_reconciliation_response,
    parse_payment_response,
    xml_to_dict,
)

logger = get_task_logger(__name__)


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
                response = requests.post(url, headers=headers, json=payload)

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
            response = requests.post(url, headers=headers, json=payload)

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
            "Reconciliation request sent: Status code {response.status_code} - Response {response.text}"
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
        # Check if payment transaction details are available and create PaymentReconciliation objects
        if pmt_trx_dtls:
            for pmt_trx_dtl in pmt_trx_dtls:
                PaymentReconciliation.objects.create(**pmt_trx_dtl)

            # Update the PaymentGatewayLog object with status and description
            PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
                status="SUCCESS",
                status_desc=f"Bill reconciliation response processed successfully. {len(pmt_trx_dtls)} reconciliation data.",
            )

        # Log the successful reconciliation response
        logger.info(
            f"Bill reconciliation response for request ID: {req_id} processed successfully."
        )

        # Update the PaymentGatewayLog object with the status and description
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="SUCCESS",
            status_desc=f"Bill reconciliation response processed successfully. No payment transactions to reconcile at this time.",
        )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the response
        # Update the PaymentGatewayLog object with the error message
        PaymentGatewayLog.objects.filter(req_id=req_id, req_type="6").update(
            status="ERROR",
            status_desc=f"Error processing bill reconciliation response: {str(e)}",
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
