import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Bill, Payment, PaymentReconciliation
from .utils import (
    compose_bill_control_number_request_payload,
    compose_acknowledgement_response_payload,
    compose_bill_reconciliation_request_payload,
    compose_bill_reconciliation_response_acknowledgement_payload,
    parse_acknowledgement_response,
    parse_final_response,
    parse_payment_response,
    parse_bill_reconciliation_request_acknowledgement,
    parse_bill_reconciliation_response,
)


logger = get_task_logger(__name__)


@shared_task
def send_mail_notification(email, subject, message):
    # Send email notification to the user
    send_mail(subject, message, settings.EMAIL_HOST_USER, [email])


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retry 5 times with an initial delay of 60 seconds
def send_bill_control_number_request(self, req_id, bill_obj):
    try:
        # Send the bill control number request to the Payment Gateway API
        url = settings.BILL_SUBMISSION_URL

        # GEPG API headers
        headers = {
            "Content-Type": "application/xml",
            "Gepg-Com": settings.GEPG_COM,
            "Gepg-Code": settings.GEPG_CODE,
            "Gepg-Alg": settings.GEPG_ALG,
        }

        # Compose the bill control number request payload
        payload = compose_bill_control_number_request_payload(req_id, bill_obj)

        # Send the bill control number request to the GEPG API
        response = requests.post(url, headers=headers, data=payload)

        # If response status is not successful, raise an exception to trigger retry
        response.raise_for_status()

        # Process the initial acknowledgement
        process_initial_acknowledgement.delay(req_id, bill_obj.bill_id, response.text)

    except requests.RequestException as e:
        # Log the error
        logger.error(f"Error sending bill control number request: {e}")

        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
        # Handle any exceptions that occur during the request or processing
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error sending bill control number request for bill ID: {bill_obj.bill_id} - {str(e)}",
        )


@shared_task
def process_initial_acknowledgement(req_id, bill_id, response_data):
    # Process the initial acknowledgement response
    # Access req_id to associate the task with the specific bill control number request
    # Check if acknowledgment indicates success or failure
    # If successful, proceed to fetch the final response
    # Otherwise, handle the failure scenario

    try:
        # Parse the initial acknowledgement response
        ack_id, req_id, ack_sts_code, ack_sts_desc = parse_acknowledgement_response(
            response_data
        )

        if ack_sts_code == "7101":  # Successfull acknowledgement
            # Wait for GEPG API to process the request and send the final response
            # Do nothing, the response will be processed by a callback
            pass
        else:
            # Any other acknowledgement status code, log and send send an email notification to developers
            logger.error(
                f"Error processing bill control number request for bill ID: {bill_id} - {ack_sts_desc}"
            )

            # Send email notification to developers
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing bill control number request for bill ID: {bill_id} - {ack_sts_desc}",
            )
    except Exception as e:
        # Handle any exceptions that occur during the processing of the acknowledgement response
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing acknowledgement response for bill ID: {bill_id} - {str(e)}",
        )


@shared_task
def process_final_response(response_data):
    # Process the final response received from the GEPG API
    # Extract control number from the response and save it to the bill object
    # Handle success/failure scenarios accordingly

    try:
        # Parse the final response
        res_id, req_id, bill_id, cust_cntr_num, res_sts_code, res_sts_desc = (
            parse_final_response(response_data)
        )

        # Send acknowledgment for the final response back to the GEPG API
        # before any further internal processing
        send_final_response_acknowledgment.delay(
            ack_id=res_id, res_id=req_id, ack_sts_code=res_sts_code
        )

        # Process the final response based on the status code
        if res_sts_code == "7101":  # Successful response
            # Update the bill object with the control number
            bill = Bill.objects.get(bill_id=bill_id)
            bill.cntr_num = cust_cntr_num
            bill.save()

        else:
            # Any other response status code, send an email notification to developers
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing final response for bill ID: {bill_id} - {res_sts_desc}",
            )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the final response
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing final response for bill ID: {bill_id} - {str(e)}",
        )


@shared_task
def send_final_response_acknowledgment(ack_id, res_id, ack_sts_code):
    # Send acknowledgment for the final response back to the Payment Gateway API

    try:
        # GEPG API URL for sending the acknowledgment
        url = settings.BILL_SUBMISSION_URL

        # GEPG API headers
        headers = {
            "Content-Type": "application/xml",
        }

        # Compose the acknowledgment response payload
        payload = compose_acknowledgement_response_payload(ack_id, res_id, ack_sts_code)

        # Send the acknowledgment response to the GEPG API
        response = requests.post(url, headers=headers, data=payload)

        # Check the response status code
        if response.status_code == 200:
            # Log the successful acknowledgment
            print("Final response acknowledgment sent successfully.")
        else:
            # Log the failure to send acknowledgment
            print("Failed to send final response acknowledgment.")
    except Exception as e:
        # Handle any exceptions that occur during the acknowledgment process
        print(f"Error sending final response acknowledgment: {str(e)}")


@shared_task
def process_bill_payment_response(response_data):
    # Process the payment response received from the GEPG API
    # Extract relevant information from the response and update payment object

    try:
        # Parse the payment response data
        (
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
        ) = parse_payment_response(response_data)

        # Update the payment object with the payment details
        payment = Payment.objects.get(bill_id=bill_id)
        payment.psp_code = psp_code
        payment.psp_name = psp_name
        payment.trx_id = trx_id
        payment.payref_id = payref_id
        payment.bill_amt = bill_amt
        payment.paid_amt = paid_amt
        payment.paid_ccy = paid_ccy
        payment.coll_acc_num = coll_acc_num
        payment.trx_date = trx_date
        payment.pay_channel = pay_channel
        payment.trdpty_trx_id = trdpty_trx_id
        payment.pyr_cell_num = pyr_cell_num
        payment.pyr_email = pyr_email
        payment.pyr_name = pyr_name
        payment.save()

    except Exception as e:
        # Handle any exceptions that occur during the processing of the payment response
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing payment response: {str(e)}",
        )


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retry 5 times with an initial delay of 60 seconds
def send_bill_reconciliation_request(self, req_id, sp_grp_code, sys_code):
    # Send the bill reconciliation request to the GEPG API
    # This task is triggered by a scheduled task for reconciliation of the previous day starting between 0600hrs to 2359hrs

    # Get the date of the previous day
    prev_day = datetime.now() - timedelta(days=1)
    trxDt = prev_day.strftime("%Y-%m-%d")

    try:
        # Send the bill reconciliation request to the Payment Gateway API
        url = settings.BILL_RECONCILIATION_URL

        # GEPG API headers
        headers = {
            "Content-Type": "application/xml",
            "Gepg-Com": settings.GEPG_COM,
            "Gepg-Code": settings.GEPG_CODE,
            "Gepg-Alg": settings.GEPG_ALG,
        }

        # Compose the bill reconciliation request payload
        payload = compose_bill_reconciliation_request_payload(
            req_id, sp_grp_code, sys_code, trxDt
        )

        # Send the bill reconciliation request to the GEPG API
        response = requests.post(url, headers=headers, data=payload)

        # If response status is not successful, raise an exception to trigger retry
        response.raise_for_status()

        # Process the bill reconciliation request acknowledgement
        process_bill_reconciliation_request_acknowledgement.delay(response.text)

    except requests.RequestException as e:
        # Log the error
        logger.error(f"Error sending bill reconciliation request: {e}")

        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
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
            # Proceed to fetch the bill reconciliation response
            pass
        else:
            # Any other acknowledgement status code, send an email notification to developers
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing bill reconciliation request - {ack_sts_desc}",
            )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the acknowledgement response
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing bill reconciliation request acknowledgement - {str(e)}",
        )


@shared_task
def process_bill_reconciliation_response(response_data):
    # Process the bill reconciliation response received from the GEPG API
    # Extract relevant information from the response and update payment reconciliation object
    pass


@shared_task
def send_bill_reconciliation_response_acknowledgement(ack_id, res_id, ack_sts_code):
    # Send acknowledgment for the bill reconciliation response back to the Payment Gateway API

    try:
        # GEPG API URL for sending the acknowledgment
        url = settings.BILL_RECONCILIATION_URL

        # GEPG API headers
        headers = {
            "Content-Type": "application/xml",
        }

        # Compose the acknowledgment response payload
        payload = compose_bill_reconciliation_response_acknowledgement_payload(
            ack_id, res_id, ack_sts_code
        )

        # Send the acknowledgment response to the GEPG API
        response = requests.post(url, headers=headers, data=payload)

        # Check the response status code
        if response.status_code == 200:
            # Log the successful acknowledgment
            logger.info(
                "Bill reconciliation response acknowledgment sent successfully."
            )
        else:
            # Log the failure to send acknowledgment
            logger.error("Failed to send bill reconciliation response acknowledgment.")

    except Exception as e:
        # Handle any exceptions that occur during the acknowledgment process
        logger.error(
            f"Error sending bill reconciliation response acknowledgment: {str(e)}"
        )
