# Phase 0 Research: Email Invoice and Receipt Delivery

This document resolves planning unknowns and records key design decisions.

## Decision: Trigger points for delivery

- **Decision**: Trigger invoice delivery when the bill becomes payable (i.e., once the bill has the required payment identifier for the customer to pay). Trigger receipt delivery when payment is confirmed and persisted.
- **Rationale**: In this codebase, the bill “payable” milestone is effectively when control number is assigned (control number is required for payment). Payment is confirmed when a `Payment` record is created.
- **Alternatives considered**:
  - Trigger invoice email immediately on bill creation: rejected because bill may not yet be payable.
  - Trigger receipt email on gateway ACK rather than persisted payment: rejected because ACK does not guarantee persistence.

## Decision: Idempotency strategy for emails

- **Decision**: Introduce a DB-backed delivery record with a uniqueness constraint covering (bill, document_type, recipient_email, event_key).
- **Rationale**: Existing workflows already experience retries and duplicate callbacks. Celery retries and duplicate inbound events must not produce multiple customer emails.
- **Alternatives considered**:
  - In-memory de-dupe (cache/Redis only): rejected due to loss on restart and hard-to-audit behavior.
  - Rely only on gateway log uniqueness: rejected because log keys are request-scoped, not delivery-scoped.

## Decision: Recipient selection policy

- **Decision**: Use conservative recipient selection rules:
  - Primary recipient: the customer email on the bill’s customer record.
  - Secondary recipient (optional and configurable): payer email captured on payment confirmation.
  - If customer and payer emails differ and policy is “customer-only”, do not send to payer.
- **Rationale**: Prevents accidental disclosure when a third party pays.
- **Alternatives considered**:
  - Always send to both customer + payer: rejected due to privacy leakage risk.

## Decision: Document delivery form

- **Decision**: Deliver documents as email attachments (PDF) with a plain-text body summary. Optionally include a URL only if it is accessible without login.
- **Rationale**: Existing receipt PDF view is login-protected; emails must be usable without requiring login.
- **Alternatives considered**:
  - Email only a link to existing PDF views: rejected because receipt view requires authentication.
  - Store generated PDFs permanently: deferred; attachments can be generated on demand at send time.

## Decision: PDF generation approach

- **Decision**: Generate PDFs from the existing HTML templates used by billing printouts.
- **Rationale**: Reuses current formatting and avoids creating new document templates.
- **Alternatives considered**:
  - Create new dedicated email templates for invoices/receipts: rejected for MVP (higher effort and risk of divergence).

## Decision: Manual re-send

- **Decision**: Manual re-send creates a new attempt record and bypasses automated idempotency for the “auto” event_key, but remains idempotent per manual attempt key.
- **Rationale**: Staff must be able to re-send when delivery failed or when customer requests it; attempts must remain auditable.
- **Alternatives considered**:
  - Allow manual re-send to reuse the automated idempotency key: rejected because it would block legitimate re-sends.

## Open Questions

None required for Phase 0. All planning clarifications are resolved for the current MVP scope.
