import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Bill, Payment, PaymentReconciliation, PaymentGatewayLog, SystemInfo
from .utils import (
    compose_bill_control_number_request_payload,
    compose_acknowledgement_response_payload,
    compose_bill_reconciliation_request_payload,
    compose_bill_reconciliation_response_acknowledgement_payload,
    parse_bill_control_number_request_acknowledgement,
    parse_bill_control_number_response,
    parse_payment_response,
    parse_bill_reconciliation_request_acknowledgement,
    parse_bill_reconciliation_response,
    load_private_key,
    xml_to_dict,
)


logger = get_task_logger(__name__)


@shared_task
def send_mail_notification(email, subject, message):
    # Send email notification to the user
    send_mail(subject, message, settings.EMAIL_HOST_USER, [email])


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
        private_key = load_private_key("security/gepgclientprivate.pfx", "passpass")

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
        pg_log = PaymentGatewayLog.objects.create(
            bill=bill,
            req_id=req_id,
            req_type="1",
            req_data=xml_to_dict(payload),
        )

        # Send the bill control number request to the GEPG API
        logger.info(f"Sending bill control number request: {payload}")
        response = requests.post(url, headers=headers, data=payload)

        # Update the PaymentGatewayLog object with the response data
        pg_log.req_ack = xml_to_dict(response.text)
        pg_log.save()
        logger.info(
            f"Bill control number request sent: Response Code - {response.status_code}, Response Text - {response.text}"
        )

        # If response status is not successful, raise an exception to trigger retry
        response.raise_for_status()

        # Process the initial acknowledgement
        process_bill_control_number_request_acknowledgement.delay(response.text)

    except requests.RequestException as e:
        logger.error(f"Error sending bill control number request: {e}")

        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
        # Handle any exceptions that occur during the request or processing of the response
        logger.error(f"Unexpected error sending bill control number request: {e}")
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
            PaymentGatewayLog.objects.filter(req_id=req_id).update(
                status="ACKNOWLEDGED",
                status_desc=ack_sts_desc,
            )
            logger.info(
                f"Bill control number request for the request ID: {req_id} was successful. Acknowledgement ID: {ack_id}"
            )
        else:
            # Any other acknowledgement status code, log and send send an email notification to developers
            PaymentGatewayLog.objects.filter(req_id=req_id).update(
                status="ACKNOWLEDGED",
                status_desc=ack_sts_desc,
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
        PaymentGatewayLog.objects.filter(req_id=req_id).update(
            status="ACKNOWLEDGED",
            status_desc=f"Error processing acknowledgement response: {str(e)}",
        )
        logger.error(
            f"Error processing acknowledgement response fo the request ID: {req_id} - {str(e)}"
        )
        send_mail_notification.delay(
            settings.DEVELOPER_EMAIL,
            "Payment Gateway API Error",
            f"Error processing acknowledgement response for the request ID: {req_id} - {str(e)}",
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
            # Log the successful response
            logger.info(
                f"Bill control number for request - {req_id} returned successfully. Bill ID: {bill_id}, Control Number: {cust_cntr_num}"
            )
            # Update the bill object with the control number
            bill = Bill.objects.get(bill_id=bill_id)
            bill.cntr_num = cust_cntr_num
            bill.save()

            # Check if bill control number request came from external system
            if bill.sys_info is not None:
                # Send control number to the external system
                url = bill.sys_info.cntrnum_response_callback
                headers = {"Content-Type": "application/json"}
                payload = {
                    "req_id": req_id,
                    "bill_id": bill_id,
                    "cntr_num": cust_cntr_num,
                }
                response = requests.post(url, headers=headers, json=payload)

                # Update the PaymentGatewayLog object with the response data
                if response.status_code == 200:
                    PaymentGatewayLog.objects.filter(req_id=req_id).update(
                        status="BILL CONTROL NUMBER REQUEST SUCCESSFUL",
                        status_desc=f"Control number sent to {bill.sys_info.name}",
                    )
                PaymentGatewayLog.objects.filter(req_id=req_id).update(
                    status="BILL CONTROL NUMBER REQUEST SUCCESSFUL",
                    status_desc=f"Error sending control number to {bill.sys_info.name}",
                )

        else:
            # Any other response status code log and send an email notification to developers
            PaymentGatewayLog.objects.filter(req_id=req_id).update(
                status="BILL CONTROL NUMBER REQUEST UNSUCCESSFUL",
                status_desc=f"Error processing final response: {res_sts_desc}",
            )
            logger.error(
                f"Error processing final response {res_id} for bill ID: {bill_id} - {bill_sts_code}: {bill_sts_desc}"
            )
            send_mail_notification.delay(
                settings.DEVELOPER_EMAIL,
                "Payment Gateway API Error",
                f"Error processing final response for bill ID: {bill_id} - {bill_sts_code}: {bill_sts_desc}",
            )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the final response
        PaymentGatewayLog.objects.filter(req_id=req_id).update(
            status="BILL CONTROL NUMBER REQUEST UNSUCCESSFUL",
            status_desc=f"Error processing final response: {str(e)}",
        )
        logger.error(
            f"Error processing final response for the request - {req_id} and  Bill ID - {bill_id}: {str(e)}"
        )
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
            url = bill.sys_info.payment_response_callback
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
                "trx_date": trx_date,
                "pay_channel": pay_channel,
                "pyr_cell_num": pyr_cell_num,
            }
            response = requests.post(url, headers=headers, json=payload)

            # Update the PaymentGatewayLog object with the response data
            if response.status_code == 200:
                PaymentGatewayLog.objects.filter(req_id=req_id).update(
                    status="PAYMENT NOTIFICATION SUCCESSFUL",
                    status_desc=f"Payment notification sent to {bill.sys_info.name}",
                )

                # Update the payment gateway log with the response data
                PaymentGatewayLog.objects.filter(req_id=req_id).update(
                    status="PAYMENT NOTIFICATION SUCCESSFUL",
                    status_desc=f"Payment notification sent to {bill.sys_info.name}",
                    res_data=response.json(),
                )

            PaymentGatewayLog.objects.filter(req_id=req_id).update(
                status="PAYMENT NOTIFICATION SUCCESSFUL",
                status_desc=f"Error sending payment notification to {bill.sys_info.name}",
            )

            # Update the payement gateway log with the response data
            PaymentGatewayLog.objects.filter(req_id=req_id).update(
                status="PAYMENT NOTIFICATION SUCCESSFUL",
                status_desc=f"Error sending payment notification to {bill.sys_info.name}",
                res_data=response.json(),
            )

        # Log the successful payment response
        logger.info(
            f"Payment response for request ID: {req_id} and Bill ID: {bill_id} processed successfully."
        )

    except Exception as e:
        # Handle any exceptions that occur during the processing of the payment response
        PaymentGatewayLog.objects.filter(req_id=req_id).update(
            status="PAYMENT NOTIFICATION UNSUCCESSFUL",
            status_desc=f"Error processing payment response: {str(e)}",
        )
        logger.error(
            f"Error processing payment response for request ID: {req_id} and Bill ID: {bill_id}: {str(e)}"
        )
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
