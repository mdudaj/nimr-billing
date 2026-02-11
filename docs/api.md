# NIMR Billing API

Base URL: `/api`

## Authentication

- **Bill submission** uses API keys via header: `Authorization: Api-Key <key>`.
- **Internal endpoints** require an admin user (DRF defaults: session or basic auth).
- **Callback endpoints** are unauthenticated.

## Endpoints

### POST `/api/bill-submission/`
Submits a bill and starts control-number processing. Requests are idempotent within 10-minute buckets.
If the bill currency is `TZS` while the revenue source item is `USD`, the server converts amounts using the latest exchange rate.

**Request body**

```json
{
  "sys_code": "SYS001",
  "bill_dept": "Finance",
  "description": "Monthly subscription",
  "revenue_source": 123,
  "currency": "TZS",
  "customer": {
    "first_name": "John",
    "middle_name": "A.",
    "last_name": "Doe",
    "cell_num": "255700000000",
    "email": "john.doe@example.com"
  }
}
```

**Responses**
- `201` Created
- `202` Accepted (duplicate in progress)
- `400` Validation error
- `500` Server error

### POST `/api/bill-cntrl-num-response-callback/`
Records a control-number response. Duplicate posts are safe.

**Request body**

```json
{
  "req_id": "REQ1",
  "bill_id": "BILL1",
  "cntrl_num": "CNTRL1",
  "bill_amt": "100.00"
}
```

**Responses**
- `200` OK (includes `duplicate: true|false`)
- `400` Missing or invalid fields
- `500` Server error

### POST `/api/bill-cntrl-num-payment-callback/`
Records a payment notification. Duplicate posts are safe by `trx_id`.

**Request body**

```json
{
  "bill_id": "BILL1",
  "psp_code": "PSP01",
  "psp_name": "Provider",
  "trx_id": "TRX123",
  "payref_id": "PAYREF1",
  "bill_amt": "100.00",
  "paid_amt": "100.00",
  "paid_ccy": "TZS",
  "coll_acc_num": "000000000000",
  "trx_date": "2025-01-01T10:00:00Z",
  "pay_channel": "BANK",
  "pay_cell_num": "255700000000"
}
```

**Responses**
- `200` OK (includes `duplicate: true|false`)
- `400` Missing or invalid fields
- `500` Server error

### GET `/api/internal/billing/bills/{bill_id}/deliveries`
Returns email delivery attempts for the bill. Requires an admin user.

**Responses**
- `200` OK
- `404` Bill not found

### POST `/api/internal/billing/bills/{bill_id}/deliveries/resend`
Enqueues a resend of a billing document. Requires an admin user.

**Request body**

```json
{
  "document_type": "INVOICE",
  "recipient_email": "optional@example.com"
}
```

**Responses**
- `202` Accepted
- `400` Invalid document type
- `404` Bill not found

## Schemas

The full OpenAPI schema is available at `docs/openapi.yaml`.
