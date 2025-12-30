# Phase 1 Data Model: Email Invoice and Receipt Delivery

This feature is primarily an addition to the existing billing domain to track outbound email deliveries.

## Existing Entities (Relevant)

### Bill

- Identifier: `bill_id` (business identifier), `id/pk` (DB identifier)
- Fields used by this feature: amount, currency, expiry date, control number, customer
- State cues:
  - “Payable”: bill has control number assigned
  - “Paid”: bill has an associated `Payment`

### Customer

- Fields used by this feature: customer email (primary delivery target), name

### Payment

- Fields used by this feature: payer email (optional delivery target), payer name/cell, payment references, payment timestamp

## New Entities (Proposed)

### BillingEmailDelivery

Represents a single delivery “slot” that must be idempotent for a given bill, document, recipient, and trigger.

### Fields

- `id` (pk)
- `bill` (FK → Bill)
- `document_type` (enum)
  - `INVOICE`
  - `RECEIPT`
- `recipient_email` (string/email)
- `event_key` (string)
  - Examples: `auto:cn_assigned`, `auto:payment_confirmed`, `manual:<uuid>`
- `status` (enum)
  - `NOT_SENT` (no recipient or suppressed by policy)
  - `PENDING` (queued)
  - `SENT` (email send succeeded)
  - `FAILED` (email send failed)
- `attempt_count` (int)
- `last_attempt_at` (datetime)
- `sent_at` (datetime, nullable)
- `failure_reason` (text, nullable)
- `metadata` (json/text; optional audit data such as subject, attachment filename, derived recipient source)

### Constraints

- Unique constraint on `(bill, document_type, recipient_email, event_key)` to guarantee idempotency for the same trigger.

### Relationships

- Many deliveries per bill (e.g., invoice and receipt; potentially multiple recipients depending on policy).

## Validation Rules

- Recipient email must be present and syntactically valid to send.
- If policy forbids sending to payer email when different from customer, suppress sending and record `NOT_SENT`.

## State Transitions

- `NOT_SENT` is terminal for a given event_key (unless manually re-sent with a new event_key).
- `PENDING` → `SENT` on successful send.
- `PENDING` → `FAILED` on failed send.
- `FAILED` may transition back to `PENDING` for retry attempts.
