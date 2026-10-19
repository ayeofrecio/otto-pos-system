# Logging, audit trail & exception table

Everything lives in the `auditlog` app. Call sites need two functions and never
need `try/except` around them (they cannot raise).

```python
from auditlog.api import audit, log_exception, get_logger
from auditlog.constants import Action, Kind, Code

audit(Action.PRICE_OVERRIDE, transaction_no=no, approver=mgr.username, old=499, new=399)
log_exception(Kind.DATA, Code.ITEM_NOT_FOUND, "Barcode not found", entity="barcode", entity_id=code)
logger = get_logger("payment")      # plain text logging -> logs/app.log
logger.exception("boom")            # ERROR+ also lands in the exception table (kind SYSTEM)
```

## Where things go

| What | Where |
|---|---|
| Business events (voids, overrides, logins, sessions, payments, ...) | `AuditLog` table, viewer `/logs/audit/` |
| Crashes + data/device/import problems | `ErrorLog` table (the exception table), viewer `/logs/errors/` |
| Everything INFO+ as text | `logs/app.log` (daily rotation, 30 days) |
| Rows that could not reach the DB | `logs/pending_db_logs.jsonl` |

Viewer pages are for Manager/Admin. Exceptions can be set NEW / REVIEWED / RESOLVED with a note.
Identical exceptions within an hour bump `count` instead of adding rows.

## Sample transactions

Illustrative rows only (terminal 001, cashier `maria`, manager `jose`). Times are examples.

### 1. Normal sale, cash

`AuditLog`:

| When | Action | User | Approver | Txn | Details |
|---|---|---|---|---|---|
| 08:02:11 | LOGIN_OK | maria | | | |
| 08:02:40 | SESSION_OPEN | maria | | | `{"opening_cash": 2000, "business_date": "2026-10-17"}` |
| 08:15:32 | PAYMENT_COMPLETE | maria | | 00000101 | `{"total": 1498, "tendered": 1500, "change": 2, "tenders": ["CASH"], "is_refund": false, "lines": 2}` |

### 2. Price override with manager PIN, then card payment

`AuditLog`:

| When | Action | User | Approver | Txn | Details |
|---|---|---|---|---|---|
| 09:10:05 | MANAGER_PIN_OK | maria | jose | | |
| 09:10:06 | PRICE_OVERRIDE | maria | | 00000102 | `{"line": 2, "item_code": "SH1001", "old": 499, "new": 399}` |
| 09:11:20 | LINE_DISC | maria | | 00000102 | `{"line": 1, "pct": 10, "type": "SC", "discount": 45}` |
| 09:12:48 | PAYMENT_COMPLETE | maria | | 00000102 | `{"total": 804, "tenders": ["VISA"], "is_refund": false, "lines": 2}` |

A card number typed anywhere in these fields is stored masked (`************1234`); keys named `pin`, `password`, `card` are stored as `***`.

### 3. Wrong manager PIN, void, and a void-previous

`AuditLog`:

| When | Action | User | Approver | Txn | Success | Details |
|---|---|---|---|---|---|---|
| 10:01:00 | MANAGER_PIN_FAIL | maria | | | no | |
| 10:01:09 | MANAGER_PIN_OK | maria | jose | | yes | |
| 10:01:10 | VOID_TRANS | maria | | 00000103 | yes | `{"amount": 640, "lines": 3}` |
| 10:20:31 | VOID_PREVIOUS | maria | | 00000101 | yes | `{"amount": 1498, "lines": 2}` |

### 4. Return / refund

`AuditLog`:

| When | Action | User | Approver | Txn | Details |
|---|---|---|---|---|---|
| 11:05:12 | MANAGER_PIN_OK | maria | jose | | |
| 11:05:13 | RETURN_ITEM | maria | | 00000104 | `{"source_transaction": "00000099", "lines": 1}` |
| 11:05:40 | PAYMENT_COMPLETE | maria | | 00000104 | `{"total": -399, "is_refund": true, "tenders": [], "lines": 1}` |

If the cashier asks to return more than was sold, nothing is changed and an exception row is written (see below).

### 5. Data problems in the exception table (`ErrorLog`)

| Kind | Code | Message | Entity | Count | Status |
|---|---|---|---|---|---|
| DATA | ITEM_NOT_FOUND | Barcode not found | barcode `4800123456789` | 3 | NEW |
| DATA | PRICE_MISSING | Item has no price | item `SH2044` | 1 | NEW |
| VALIDATION | BARCODE_INVALID | Non-numeric barcode rejected | barcode `48A0123` | 1 | NEW |
| DATA | RETURN_INVALID | Return quantity exceeds sold quantity | transaction `00000099` | 1 | REVIEWED |
| DATA | BIZDATE_FALLBACK | get_business_date failed; using calendar date | | 2 | NEW |
| DATA | TXN_LOG_FAILED | TransactionService log failed: ... (with traceback) | transaction `00000105` | 1 | RESOLVED |

The first row has `count` 3 because the same barcode was scanned three times within the hour. A manager can open `/logs/errors/`, filter by code, and set a row to REVIEWED or RESOLVED with a note.

### 6. Device failure and a crash

| Kind | Code | Message | Entity |
|---|---|---|---|
| DEVICE | PRINTER_FAIL | Printer error: ... (with traceback) | receipt `00000105` |
| DEVICE | DRAWER_FAIL | Cash drawer pulse failed: ... | |
| SYSTEM | UNHANDLED | Internal Server Error: /pos/cart/add/ (with traceback) | |

The sale itself still completes when the printer fails; the problem is recorded so someone can follow up.

### 7. End of day

`AuditLog`:

| When | Action | User | Details |
|---|---|---|---|
| 21:00:02 | X_READ | maria | |
| 21:30:15 | SESSION_CLOSE | maria | `{"closing_cash": 8450, "expected_cash": 8500, "variance": -50, "notes": "short 50"}` |
| 21:30:18 | Z_READ | maria | |
| 21:30:19 | LOGOUT | maria | |

### 8. Connection drop in the middle of a sale

Cart already has items; the network or database drops for about 90 seconds.

`AuditLog` (sent by the browser after the connection returns):

| When | Action | User | Txn | Details |
|---|---|---|---|---|
| 14:22:10 | CONNECTION_LOST | maria | 00000106 | `{"lost_at": "2026-10-17T14:22:10", "page": "/pos/"}` |
| 14:23:41 | CONNECTION_RESTORED | maria | 00000106 | `{"seconds": 91, "restored_at": "2026-10-17T14:23:41"}` |

What the cashier sees: a red banner "Do NOT retry the payment" while down, then "Connection restored. Please verify the cart" with a Reload cart link. If the sale had actually been completed before the drop, the banner says so ("already COMPLETED, do not charge again").

If the database is down, server-side rows are written to `logs/pending_db_logs.jsonl`, one JSON line each:

```json
{"model": "audit", "fields": {"action": "PAYMENT_COMPLETE", "username": "maria", "transaction_no": "00000106", "details": {"total": 640}, "created_at": "2026-10-17T14:22:30"}}
```

After `python manage.py replay_pending_logs` they appear in the tables with their original time.

## Add a new audit event or exception (3 steps)

1. Add one line to `Action` (business event) or `Code` (problem type) in `auditlog/constants.py`.
2. Call `audit(Action.X, ...)` / `log_exception(Kind.Y, Code.X, "message", entity=..., entity_id=...)`.
3. Done - no migration (enums are not model choices), the viewer filters pick it up.

## Configuration

Defaults are in `auditlog/conf.py`; override any key in the `AUDITLOG` dict in
`config/settings/base.py`. `.env`: `LOG_LEVEL` (default INFO).
Redaction: keys in `redact_keys` become `***`, 13-19 digit numbers are masked, in every row and log line.

## When the database is unreachable

Writes fall back to `logs/pending_db_logs.jsonl` (DB writes pause for `breaker_seconds`
so requests do not wait on timeouts). Run `python manage.py replay_pending_logs` (Task Scheduler,
every few minutes) to load them back with their original timestamps.

The cashier page runs `static/sales/connection.js`: it pings `/logs/health/`, shows a banner when the
server/DB stops answering, and on recovery asks the cashier to verify the cart and checks
`/logs/transaction-status/<no>/` (completed / open / not_found) so a sale is not charged twice.
Drop and recovery are recorded as `CONNECTION_LOST` / `CONNECTION_RESTORED`.

## Maintenance

`python manage.py purge_logs` (defaults: audit 730 days, exceptions 90 days) - schedule daily.

## Notes

- `audit()` rows written inside a `transaction.atomic()` that later rolls back are rolled back too.
- Only the effective (later) duplicate views in `sales/views.py` for returns are the live ones; the
  earlier duplicates are shadowed. Price override / return audit calls exist in both, harmlessly.
