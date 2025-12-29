# Feature Specification: Email Invoice and Receipt Delivery

**Feature Branch**: `001-email-invoice-receipt`  
**Created**: 2025-12-29  
**Status**: Draft  
**Input**: User description: "Enable emailing invoices and receipts to customers with idempotent delivery and no duplicate sends"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Receipt After Payment (Priority: P1)

As a payer/customer, I want to automatically receive an email receipt after a bill payment is confirmed so I have proof of payment without needing to log in or contact support.

**Why this priority**: Payment proof is the highest-value document and the most common support request when missing.

**Independent Test**: Can be fully tested by confirming a payment for a bill and verifying that exactly one receipt email is delivered to the intended recipient(s).

**Acceptance Scenarios**:

1. **Given** a bill has a valid recipient email address on file, **When** the system confirms payment for that bill, **Then** the recipient receives a receipt email containing a human-readable payment summary and a downloadable receipt document.
2. **Given** the system receives duplicate or retried payment confirmations for the same bill/payment, **When** the receipt-delivery workflow runs multiple times, **Then** only one receipt email is sent per intended recipient.
3. **Given** a bill payment is confirmed but no valid recipient email address exists, **When** the receipt-delivery workflow runs, **Then** no email is sent and the delivery outcome is recorded as “not sent” with a clear reason.

---

### User Story 2 - Receive Invoice After Bill Is Issued (Priority: P2)

As a customer, I want to receive an email invoice once the bill is ready to pay so I can pay using the provided identifiers and instructions.

**Why this priority**: Customers need a clear invoice containing the required payment identifiers to complete payment accurately.

**Independent Test**: Can be fully tested by creating a bill, marking it as ready for payment, and verifying that exactly one invoice email is delivered with correct bill identifiers.

**Acceptance Scenarios**:

1. **Given** a bill becomes ready for payment (including its required payment identifier), **When** the invoice-delivery workflow runs, **Then** the customer receives an invoice email containing a bill summary and a downloadable invoice document.
2. **Given** the system receives duplicate or retried bill-ready events for the same bill, **When** the invoice-delivery workflow runs multiple times, **Then** only one invoice email is sent per customer.

---

### User Story 3 - Delivery Status and Manual Re-Send (Priority: P3)

As authorized staff (authenticated staff users), I want to see whether an invoice/receipt email was sent (and why it failed) and to be able to manually re-send when needed.

**Why this priority**: When email delivery fails, staff need a fast recovery path that does not require reprocessing payments or regenerating bills.

**Independent Test**: Can be tested by forcing a delivery failure, confirming the failure is visible in delivery status, and triggering a manual re-send that results in a new delivery attempt.

**Acceptance Scenarios**:

1. **Given** an invoice/receipt delivery attempt failed, **When** authorized staff request a re-send, **Then** the system performs a new delivery attempt and records it as a separate attempt from the original.

### Edge Cases

- A bill has an email address but it is malformed or rejected by the email provider.
- Email delivery is temporarily unavailable (provider outage or transient failure).
- A bill is cancelled after an invoice email was already sent.
- Payment confirmation arrives more than once, out of order, or significantly delayed.
- Multiple recipients are possible (e.g., customer vs payer email) and the system must avoid leaking information to unintended recipients.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST determine the recipient(s) for invoice and receipt delivery using stored customer/payer contact information and configured rules.
-  Configured rules are implemented via Django settings (with the “Default Policy (Recipient Selection)” as the default); no admin-managed rules UI is included in this feature.
- **FR-002**: System MUST generate an invoice document for a bill once it is ready for payment, including the bill identifier(s), amount, currency, due/expiry information, and payment instructions.
- **FR-003**: System MUST generate a receipt document for a bill once payment is confirmed, including the bill identifier(s), amount paid, currency, payment reference(s), and payment date/time.
- **FR-004**: System MUST deliver invoice and receipt emails asynchronously so that bill issuance and payment processing are not blocked by email delivery.
- **FR-005**: System MUST ensure idempotent delivery such that the same invoice/receipt is not emailed more than once per bill per recipient for the same triggering event, even if upstream events are duplicated or retried.
- **FR-006**: System MUST record delivery status for each invoice/receipt email (at minimum: not sent, pending, sent, failed) with timestamps and a failure reason when applicable.
- **FR-007**: System MUST allow authorized staff to manually trigger a re-send for a specific bill document type (invoice or receipt), creating a new delivery attempt without duplicating automated idempotent sends.
- **FR-008**: System MUST include a human-readable summary in the email body (key bill/payment details) so users can confirm correctness without opening the attachment.
- **FR-009**: System MUST support configurable email sender identity and subject/body wording appropriate for invoices and receipts.
- **FR-010**: System MUST prevent sending billing documents to unintended recipients (e.g., by applying conservative recipient-selection rules when payer and customer emails differ).

### Default Policy (Recipient Selection)

- By default, documents are sent to the bill’s customer email address only.
- Sending to payer email is disabled by default; if enabled, it MUST follow a conservative policy to avoid disclosure (e.g., only send to payer when payer email matches customer email, or when explicitly allowed by a configured policy).

### Authorization Policy (Staff Features)

- Delivery status and manual re-send are available only to authenticated staff users (authorization rules must be explicit and auditable).

### Acceptance Criteria

1. **FR-001**: **Given** a bill and associated contacts, **When** an invoice/receipt event occurs, **Then** the system selects recipients according to configured rules and records who would be contacted.
2. **FR-002**: **Given** a bill ready for payment, **When** an invoice is generated for delivery, **Then** the invoice includes bill identifiers, amounts, currency, expiry information, and payment instructions.
3. **FR-003**: **Given** a confirmed payment, **When** a receipt is generated for delivery, **Then** the receipt includes bill identifiers, paid amount, currency, payment references, and payment timestamp.
4. **FR-004**: **Given** bill issuance or payment confirmation, **When** delivery is initiated, **Then** the originating workflow completes without waiting on email delivery to finish.
5. **FR-005**: **Given** duplicate triggering events, **When** delivery runs multiple times, **Then** only one email is delivered per bill/document type/recipient for the same event.
6. **FR-006**: **Given** a delivery attempt occurs, **When** it completes (success or failure), **Then** status, timestamps, and a failure reason (if any) are recorded.
7. **FR-007**: **Given** a failed or missing delivery, **When** authorized staff request re-send, **Then** a new attempt is created and tracked separately from automated delivery.
8. **FR-008**: **Given** an invoice/receipt email is delivered, **When** a recipient reads it, **Then** key bill/payment details are visible in the message body.
9. **FR-009**: **Given** delivery configuration is updated, **When** new emails are delivered, **Then** sender identity and messaging reflect the updated configuration.
10. **FR-010**: **Given** payer and customer emails differ, **When** the system applies recipient rules, **Then** it does not send documents to recipients outside the configured policy.

### Key Entities *(include if feature involves data)*

- **Billing Document**: A customer-facing representation of a bill (“invoice”) or payment confirmation (“receipt”), including identifying references and display-ready details.
- **Delivery Record**: Tracks the delivery state of a specific document type for a specific bill and recipient, including idempotency identity, timestamps, status, and failure reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of receipt emails are delivered within 5 minutes of payment confirmation; at least 99% within 30 minutes.
- **SC-002**: Duplicate invoice/receipt emails caused by repeated upstream events occur in 0% of cases in normal operation (idempotency prevents duplicates).
- **SC-003**: Reduce “receipt not received” support requests by at least 50% within 3 months of rollout.
- **SC-004**: Authorized staff can determine invoice/receipt delivery status for any bill in under 30 seconds.

## Assumptions

- Some customers may not have an email address on file; in such cases the system will not send emails and will record the reason.
- Delivery will be retried for transient failures; persistent failures require manual re-send.
- Documents will be delivered in a form usable without requiring the recipient to log in (e.g., as an email attachment and/or equivalent downloadable content).

## Dependencies

- Bill issuance and payment confirmation events are available and include stable identifiers.
- An operational email delivery service is configured for the environment.

## Out of Scope

- SMS notifications.
- Changes to external integrating-system callbacks beyond continuing existing behavior.
- Redesign of existing billing screens unrelated to delivery status and re-send.
