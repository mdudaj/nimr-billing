# Quickstart: Email Invoice and Receipt Delivery

This quickstart describes how to verify the feature in a development/staging environment.

## Prerequisites

- Working Django app + migrations applied
- Running Celery worker + broker
- Email backend configured for the environment (SMTP or console)

## Configuration Checklist

- Set sender identity (e.g., `EMAIL_HOST_USER`) and email backend settings
- Ensure `PUBLIC_URL` is correct (only used if links are included)
- Ensure Celery is running (invoice/receipt delivery is asynchronous)

## How to Test (MVP)

### 1) Invoice delivery (bill becomes payable)

1. Create a bill with a customer email.
2. Progress the bill to “payable” (control number assigned).
3. Verify:
   - Exactly one invoice delivery record exists per intended recipient.
   - An invoice email is sent with a PDF attachment and body summary.

### 2) Receipt delivery (payment confirmed)

1. Confirm payment for a bill (persist a payment record).
2. Verify:
   - Exactly one receipt delivery record exists per intended recipient.
   - A receipt email is sent with a PDF attachment and body summary.

### 3) Idempotency (duplicate events)

1. Re-trigger the same payable/payment event.
2. Verify:
   - No duplicate email is sent.
   - Delivery record indicates the original send and ignores duplicates.

### 4) Manual re-send

1. For a bill with a failed delivery, trigger manual re-send.
2. Verify:
   - A new attempt is recorded.
   - Email send is re-attempted.

## Troubleshooting

- If no emails are sent, check Celery worker logs and broker connectivity.
- If a receipt link is unusable, ensure receipt delivery includes an attachment (receipt PDFs should not require recipient login).
