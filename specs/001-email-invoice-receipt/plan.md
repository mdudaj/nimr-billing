# Implementation Plan: Email Invoice and Receipt Delivery

**Branch**: `001-email-invoice-receipt` | **Date**: 2025-12-29 | **Spec**: specs/001-email-invoice-receipt/spec.md
**Input**: Feature specification from `/specs/001-email-invoice-receipt/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Add a reliable, asynchronous, idempotent workflow to email invoice and receipt documents to customers/payers, with delivery status tracking and an authorized manual re-send capability.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.10  
**Primary Dependencies**: Django 4.2, Django REST Framework, Celery, Redis, django-weasyprint/WeasyPrint, requests  
**Storage**: SQLite (local dev via db.sqlite3) and PostgreSQL (production via psycopg2-binary)  
**Testing**: Django test runner (TestCase/APITestCase patterns already present)  
**Target Platform**: Linux server (Dockerized deployments supported)  
**Project Type**: Web application (Django server-rendered pages + DRF API + Celery workers)  
**Performance Goals**: Receipt emails delivered within minutes of payment confirmation (see SC-001)  
**Constraints**: Avoid duplicate email sends on retries/duplicate callbacks; do not block gateway callback processing; minimal disruption to existing gateway integrations  
**Scale/Scope**: Incremental feature within existing billing workflow; no new end-user UI beyond delivery status + re-send for authorized staff

Policy defaults (for determinism in implementation):

- Default recipient policy: send to customer email only; payer email sending is disabled by default.
- Staff-only capabilities: delivery status and re-send require authenticated staff authorization.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution file `.specify/memory/constitution.md` is currently a placeholder template (no concrete enforceable principles). Gates are therefore limited to standard engineering quality checks for this repo.

GATE CHECKS (effective for this plan):

- Must not introduce duplicate customer communications for a single bill event (idempotency required).
- Must keep payment/callback workflows non-blocking (email delivery async).
- Must preserve existing integrating-system callbacks behavior (out of scope to change).

Status: PASS (no known violations; design includes idempotency + async delivery and preserves existing callbacks).

Post-Phase-1 Re-check: PASS (Phase 0/1 artifacts generated; no additional constraints discovered).

## Project Structure

### Documentation (this feature)

```text
specs/001-email-invoice-receipt/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
accounts/
api/
auth/
billing/
core/
home/
templates/
static/
manage.py
requirements.txt
docker-compose.yml
```

**Structure Decision**: Web application (Django). This feature primarily impacts the `billing/` app (tasks, models, views/templates) and may add a small internal contract for staff actions.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ----------------------------------- |
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |

## Phase 2 Planning (Output Only)

This plan produces Phase 0 and Phase 1 artifacts. Phase 2 implementation tasks will be derived into `tasks.md` by `/speckit.tasks`.

Planned implementation work (high-level):

1. Add a delivery record model with a strict idempotency key.
2. Add Celery tasks to generate and send invoice/receipt emails with attachments.
3. Wire triggers into existing control-number and payment processing flows.
4. Add staff-facing delivery status + re-send surface (admin or minimal protected endpoint).
5. Add tests: idempotency, retry behavior, recipient selection, and document generation.
