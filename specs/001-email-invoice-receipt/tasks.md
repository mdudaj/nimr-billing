---

description: "Task list for Email Invoice and Receipt Delivery"

---

# Tasks: Email Invoice and Receipt Delivery

**Input**: Design documents from `/specs/001-email-invoice-receipt/`

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create delivery settings defaults in core/settings.py (default recipient policy: customer-only; payer delivery disabled by default; sender name)
- [X] T002 Add internal docs links for feature in README.md (reference specs/001-email-invoice-receipt/quickstart.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T003 Add BillingEmailDelivery model in billing/models.py (fields, statuses, unique constraint)
- [ ] T004 Create Django migration for BillingEmailDelivery under billing/migrations/ (auto-named migration file)
- [ ] T005 [P] Register BillingEmailDelivery in billing/admin.py (readable list display + filters)
- [ ] T006 Add recipient selection helper in billing/utils.py (returns recipient emails + suppression reason)
- [ ] T007 Add PDF generation helpers for invoice/receipt in billing/utils.py (wrap existing generate_pdf for required templates)
- [ ] T008 Add Celery task to send bill document emails in billing/tasks.py (attach PDF bytes, update delivery record)
- [ ] T009 Add internal delivery serializers in api/serializers.py for BillingEmailDelivery
- [ ] T010 Add internal delivery views in api/views.py (list deliveries, request resend) restricted to authenticated staff users
- [ ] T011 Add internal delivery routes in api/urls.py for /api/internal/billing/bills/{bill_id}/deliveries and /resend

**Checkpoint**: Delivery infrastructure exists (model + task + internal endpoints) and can be used by user-story triggers.

---

## Phase 3: User Story 1 - Receive Receipt After Payment (Priority: P1) 🎯 MVP

**Goal**: Automatically email a receipt PDF after payment is confirmed, without duplicates.

**Independent Test**: Confirm a payment for a bill and verify exactly one receipt email is sent per intended recipient, even if the payment callback is replayed.

- [ ] T012 [US1] Create receipt delivery enqueue helper in billing/tasks.py (event_key auto:payment_confirmed, creates PENDING/NOT_SENT delivery records)
- [ ] T013 [US1] Wire receipt delivery trigger into billing/tasks.py process_bill_payment_response (after Payment is created)
- [ ] T014 [US1] Ensure idempotency on receipt send in billing/tasks.py using BillingEmailDelivery unique key (no duplicate emails on retries)
- [ ] T015 [US1] Record delivery outcomes in billing/models.py BillingEmailDelivery (attempt_count, sent_at, failure_reason)
- [ ] T016 [P] [US1] Update receipt email subject/body composition in billing/utils.py (include bill_id, amount, payment refs)

**Checkpoint**: Receipt emails are sent once per event per recipient; missing/invalid email results in NOT_SENT with reason.

---

## Phase 4: User Story 2 - Receive Invoice After Bill Is Issued (Priority: P2)

**Goal**: Email a payable invoice (with control number) once the bill is ready to pay.

**Independent Test**: Assign a control number to a bill and verify exactly one invoice email is sent with correct identifiers, even if the control-number callback is replayed.

- [ ] T017 [US2] Create invoice delivery enqueue helper in billing/tasks.py (event_key auto:cn_assigned)
- [ ] T018 [US2] Wire invoice delivery trigger into billing/tasks.py process_bill_control_number_response (after Bill.cntr_num is saved)
- [ ] T019 [US2] Generate invoice PDF using existing template in billing/utils.py (bill transfer/printout template that includes control number)
- [ ] T020 [US2] Ensure idempotency on invoice send in billing/tasks.py using BillingEmailDelivery unique key
- [ ] T021 [P] [US2] Update invoice email subject/body composition in billing/utils.py (include bill_id, control number, amount, expiry)

**Checkpoint**: Invoice emails are sent once per event per recipient; duplicates are suppressed.

---

## Phase 5: User Story 3 - Delivery Status and Manual Re-Send (Priority: P3)

**Goal**: Allow authorized staff to view delivery status and request a manual re-send.

**Independent Test**: Force a delivery failure and use the internal endpoint to re-send; confirm a new attempt is created and email is attempted again.

- [ ] T022 [US3] Implement GET delivery list response in api/views.py for bill_id (matches contracts/openapi.internal-delivery.yaml)
- [ ] T023 [US3] Implement POST resend in api/views.py (creates manual event_key, queues send for requested document_type)
- [ ] T024 [US3] Support optional recipient_email override in api/views.py (otherwise use policy-derived recipients)
- [ ] T025 [US3] Add authorization checks for internal endpoints (authenticated staff users only) in api/views.py
- [ ] T026 [US3] Ensure manual re-send creates a new delivery attempt (manual:{uuid}) without breaking automated idempotency

**Checkpoint**: Staff can inspect deliveries and request re-send with auditable attempts.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T027 [P] Improve logging around delivery attempts in billing/tasks.py (include bill_id, document_type, recipient)
- [ ] T030 Add SC-001 measurement hooks: persist enqueue/sent timestamps on BillingEmailDelivery and add a quickstart verification step that checks delivery time buckets (<=5m, <=30m)
- [ ] T028 Handle cancelled bills: suppress new invoice sends and record NOT_SENT in billing/tasks.py
- [ ] T029 Validate quickstart scenarios in specs/001-email-invoice-receipt/quickstart.md and update if needed

---

## Dependencies & Execution Order

### User Story Completion Order

- US1 (P1) depends on Phase 2 Foundational.
- US2 (P2) depends on Phase 2 Foundational.
- US3 (P3) depends on Phase 2 Foundational and benefits from US1/US2 existing delivery behavior.

### Suggested MVP Scope

- MVP = Phase 1 + Phase 2 + US1 (receipt emails).

---

## Parallel Execution Examples

### US1 (Receipt)

- Run in parallel:
  - T016 [P] Update receipt email body composition in billing/utils.py
  - (Once foundational is in) T012 receipt enqueue helper in billing/tasks.py

### US2 (Invoice)

- Run in parallel:
  - T021 [P] Update invoice email body composition in billing/utils.py
  - (Once foundational is in) T017 invoice enqueue helper in billing/tasks.py

### Foundational

- Run in parallel:
  - T005 [P] Admin registration in billing/admin.py
  - T009 serializers in api/serializers.py

---

## Implementation Strategy

1. Complete Phase 2 Foundational (model + email send task + internal endpoints).
2. Implement US1 (receipt emails) and validate idempotency via duplicate callback replay.
3. Implement US2 (invoice emails) and validate idempotency via duplicate callback replay.
4. Implement US3 (delivery status + manual re-send).
5. Final polish tasks.

## Format Validation

All tasks above follow: `- [ ] T### [P?] [US?] Description with file path` (setup/foundational/polish omit [US?] labels by design).
