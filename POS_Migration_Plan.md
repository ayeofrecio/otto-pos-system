# POS System Migration Plan: Clarion → Django/Python

## Project Overview

| Detail | Info |
|---|---|
| **Timeline** | 2–3 weeks |
| **Stack** | Django + MySQL + Django REST Framework |
| **Team** | You (lead) + 1 remote co-developer |
| **POS Type** | Standalone with FTP-based updates |
| **Hardware** | Dot matrix printer, barcode scanner |
| **Domain** | Shoe retail (SKU + size + color variants) |

---

## Architecture

Before coding, agree on this structure:

```
pos_project/
├── core/          → shared models, utilities
├── inventory/     → products, SKU, sizes, colors
├── sales/         → transactions, cart, receipts
├── users/         → auth, roles, cashier sessions
├── reports/       → daily reports, Z-readings
├── settings_app/  → store config, printer, FTP sync
└── templates/
    ├── pos/       → cashier frontend
    └── admin/     → back office
```

> Use **Git + GitHub** as your coordination hub. You review all PRs before merge. Co-dev works on feature branches only.

---

## Django Project Settings Structure

Split settings from day one so both devs never fight over configuration.

```
pos_project/
└── pos_project/
    └── settings/
        ├── __init__.py   (empty)
        ├── base.py       → installed apps, models, templates, static, logging skeleton
        ├── dev.py        → DEBUG=True, local MySQL or SQLite, ALLOWED_HOSTS=['*']
        └── prod.py       → DEBUG=False, strict ALLOWED_HOSTS, WhiteNoise, file logging
```

**`dev.py` and `prod.py` both start with:**
```python
from .base import *
```

**`.env` controls which settings file loads:**
```
DJANGO_SETTINGS_MODULE=pos_project.settings.dev   # co-dev uses this
DJANGO_SETTINGS_MODULE=pos_project.settings.prod  # production machine uses this
```

**Rules:**
- Both devs use `dev.py` locally — never `prod.py`
- Co-dev **never edits** `prod.py`; only you touch it
- `base.py` contains no secrets — all credentials come from `.env` via `python-dotenv`
- A shared `.env.example` (no real values) is committed to git; actual `.env` is gitignored

---

## PHASE 0 — Legacy Clarion Data Extraction & Migration
### Pre-work (Before Week 1) | 🔴 YOU handle this

Do this before writing a single line of Django code. You cannot design accurate models without knowing exactly what data lives in Clarion today.

### Tasks
- **Audit the Clarion database:** List all tables, fields, and data types. Prioritize: products, variants, prices, barcodes, transaction history, cashiers, store config.
- **Export product catalog to CSV:** SKU, barcode, product name, size, color, price, active flag. This becomes your Phase 1 seed data and your Phase 3 mapping reference.
- **Export transaction history:** Transaction headers (date, cashier, total, receipt no) and lines (SKU, qty, price). Decide how many years to carry over — 1 year is usually enough for reporting; more increases import time significantly.
- **Build a Clarion → Django field mapping table** (see template below).
- **Write a one-time import script:** `management/commands/import_clarion.py` — runs once at go-live, maps CSV rows to Django models, skips duplicates on re-run.
- **Frozen history rule:** Imported historical transactions are read-only. They have no `POSSession` link, void logic does not apply to them, and reports label them as "Migrated."

### Field Mapping Template

| Clarion Field | Django Model | Django Field | Notes |
|---|---|---|---|
| `PROD_CODE` | `Product` | `base_sku` | Primary lookup key |
| `PROD_NAME` | `Product` | `name` | |
| `BARCODE` | `ProductVariant` | `barcode` | One per size/color combo |
| `SIZE_CODE` | `Size` | `label` | Normalize to standard labels |
| `COLOR_CODE` | `Color` | `name` | |
| `SELL_PRICE` | `ProductVariant` | `price_override` | |
| `ACTIVE_FLAG` | `Product` | `is_active` | |
| `TXN_NO` | `SalesTransaction` | `receipt_no` | Prefix with "CLR-" to avoid collision |
| `TXN_DATE` | `SalesTransaction` | `business_date` | |
| `TXN_TOTAL` | `SalesTransaction` | `total` | |

### Deliverable
- CSV exports of all Clarion products and transactions (backed up in two places)
- Completed field mapping table
- Tested `import_clarion.py` that loads products cleanly into a fresh Django DB
- Known record counts documented (e.g. "4,312 product variants, 18 months of transactions")

> **Why you:** Only you have access to the Clarion system and understand its data quirks. Dirty data discovered here (duplicate SKUs, missing barcodes, inconsistent size labels) will break the Django schema if not caught now.

---

## PHASE 1 — Foundation & Core Models
### Week 1, Days 1–2 | 🔴 YOU handle this

This is the skeleton everything depends on. **Do not delegate this.**

### Tasks
- Django project setup, MySQL connection, `.env` config
- Core models:
  - `Product` (name, SKU, base price, is_active)
  - `ProductAttribute` (color, size as separate dimension tables)
  - `ProductVariant` (SKU + size + color combination, stock qty, price override)
  - `User` + `UserRole` (admin, manager, cashier)
  - `Store` config model (store name, TIN, address, printer port, FTP settings)
- Django admin registration for all models
- MySQL schema finalized and migrations run

### Deliverable
Working Django project, all migrations complete. Django admin can CRUD products with sizes and colors.

> **Why you:** The variant/attribute model for shoes is the trickiest design decision. A wrong schema here breaks everything downstream.

### Shoe Variant Model — Full Schema Spec

This is the most critical design in the entire project. Here is the complete intended structure with example data:

```
Color
  id | name      | hex_code
  ---|-----------|----------
  1  | Black     | #000000
  2  | White     | #FFFFFF
  3  | Red       | #CC0000

Size
  id | label | sort_order
  ---|-------|------------
  1  | 5     | 10
  2  | 6     | 20
  3  | 7     | 30
  4  | 7.5   | 35
  5  | 8     | 40
  6  | 9     | 50
  7  | 10    | 60
  8  | 10.5  | 65

Product
  id | name              | base_sku | base_price | is_active
  ---|-------------------|----------|------------|----------
  1  | Nike Air Force 1  | NAF1     | 3500.00    | True
  2  | Adidas Stan Smith | ADSS     | 3200.00    | True

ProductVariant
  id | product | color | size | sku          | barcode       | price_override | stock_qty | central_id | last_synced_at
  ---|---------|-------|------|--------------|---------------|----------------|-----------|------------|----------------
  1  | 1       | 1     | 2    | NAF1-BLK-6   | 4901234560012 | NULL           | 3         | CEN-00101  | 2026-02-18
  2  | 1       | 1     | 3    | NAF1-BLK-7   | 4901234560029 | NULL           | 5         | CEN-00102  | 2026-02-18
  3  | 1       | 2     | 3    | NAF1-WHT-7   | 4901234560036 | 3800.00        | 2         | CEN-00103  | 2026-02-18
```

**Key design decisions:**

| Decision | Choice | Reason |
|---|---|---|
| Barcode on variant, not product | ✅ Variant | Each size/color combo has its own barcode label in shoe retail |
| `price_override` nullable | ✅ Nullable | NULL means "use `Product.base_price`"; only set when a variant has a different price |
| `sort_order` on Size | ✅ Yes | Prevents alphabetical sort ("10" before "5"); controls popup display order |
| `central_id` on ProductVariant | ✅ Yes | Required for sync upsert — matches local record to central system record |
| Separate Color/Size tables | ✅ Yes | Enables filtering ("show all size 7s"), reporting by color, and future additions |

**Required database indexes:**
- `ProductVariant.barcode` — fast scanner lookup (most frequent query)
- `ProductVariant.sku` — fast manual SKU entry lookup
- `ProductVariant.central_id` — fast sync upsert matching
- `ProductVariant(product, color, size)` — unique constraint to prevent duplicates

---

## PHASE 2 — User Auth & Session Management
### Week 1, Days 2–3 | 🟢 GIVE TO CO-DEV

Well-defined scope, low risk to delegate.

### Tasks
- Login/logout views (Django session-based, no JWT needed since standalone)
- User roles and permission decorators (`@cashier_required`, `@manager_required`)
- **Day Session model:** `POSSession` (opened_by, date_opened, date_closed, opening_cash, closing_cash, status)
- Midnight sale logic: if current time is 00:00–04:00, prompt cashier "Add to previous day?" → session stays linked to prior business date
- Force open session before any sale can proceed
- Close session (Z-reading trigger) with manager PIN confirmation

### Spec to Give Co-Dev

```
Model: POSSession
- session_id
- cashier (FK User)
- business_date (Date, NOT DateTime)
- opened_at (DateTime)
- closed_at (DateTime, nullable)
- opening_cash (Decimal)
- closing_cash (Decimal, nullable)
- status: OPEN / CLOSED

Rule: business_date = today if hour >= 4, else yesterday
```

---

## PHASE 3 — Central Database Integration & Local Sync
### Week 1, Days 3–5 | 🔴 YOU define, 🟢 Co-dev builds engine

Since the central system already maintains the product database, Phase 3 is about **connecting to it reliably** and keeping the local POS in sync. The POS should never depend on a live connection to ring a sale.

### The Core Question to Decide First

> Can the POS always connect to the central DB in real time, or does it need a local copy?

Since the POS is standalone with FTP-based updates, the safe assumption is **local copy with periodic sync.**

---

### Part A — Understand the Central DB Schema | 🔴 YOU
- Map the central system's product tables to your Django models from Phase 1
- Identify which fields you need: product name, SKU, barcode, size, color, price, active status
- Confirm with the central system owner: what is the export format — direct MySQL read, CSV dump, or JSON over FTP?
- This mapping is critical — **do this yourself before handing anything to co-dev**

### Part B — Local Mirror Models | 🔴 YOU
- Adjust Phase 1 `ProductVariant` and `Product` models to include a `central_id` or `external_sku` field for mapping back to the source
- Add a `last_synced_at` timestamp on synced models
- These become your **read-only local cache** — the POS never writes product data, only reads it

### Part C — Sync Engine | 🟢 CO-DEV
Once you've defined the data contract (what comes in and in what format), hand this to co-dev:
- Pull product/variant data from central source (via FTP file drop, direct MySQL connection, or whatever the central system supports)
- Upsert logic: insert new, update changed, soft-deactivate removed products
- Sync log: timestamp, records updated, errors
- Manual **"Sync Now"** button in POS back office
- Auto-sync on POS startup

### Part D — Sync Conflict Rules | 🔴 YOU define, 🟢 Co-dev implements
Define these rules clearly before co-dev touches the sync engine:
- What happens if a price changes mid-day? (Apply immediately or next business day?)
- What if a variant is deactivated centrally but has pending sales today?
- **Who wins on conflict — always the central system**

### Phase 3 Delegation Summary

| Task | Who |
|---|---|
| Central DB schema mapping | **YOU** |
| Local mirror model adjustments | **YOU** |
| Sync engine (upsert logic) | Co-dev |
| Sync UI (manual trigger, log view) | Co-dev |
| Conflict rules definition | **YOU** |

---

## PHASE 4 — POS Cashier Frontend (Core Sales)
### Week 1 Day 5 – Week 2 Day 2 | 🔴 YOU handle this

This is the heart of the system. **Keep control.**

### Tasks
- Cashier screen layout (product search, cart, totals)
- Barcode scanner input handling (HTML input field that auto-captures scanner keystrokes — scanners send Enter at end)
- Manual item search by SKU, name, or barcode
- **Shoe variant selector:** when a product is scanned/selected, if multiple sizes/colors exist → popup to select the specific variant
- Add to cart, change qty, remove item
- Discount per line and per transaction (with manager override PIN for discounts above threshold)
- Payment screen: cash tendered → change calculation; support multiple payment types (see below)
- Transaction save: `SalesTransaction` + `SalesTransactionLine`
- Official receipt number generation (auto-increment, configurable prefix)

### Key Models

```
SalesTransaction
- transaction_id
- session (FK POSSession)
- cashier (FK User)
- business_date
- created_at
- subtotal, discount_amount, total
- amount_tendered, change
- status: COMPLETED / VOIDED
- receipt_no

SalesTransactionLine
- transaction (FK SalesTransaction)
- variant (FK ProductVariant)
- qty
- unit_price
- discount
- line_total

PaymentLine
- transaction (FK SalesTransaction)
- payment_type: CASH / CARD / GCASH / OTHER
- amount (Decimal)
- reference_no (CharField, nullable — required for CARD and GCASH)
```

### Payment Method Rules

| Scenario | Behavior |
|---|---|
| Cash only | Single `PaymentLine` with `payment_type=CASH`; change = tendered − total |
| Card only | Single `PaymentLine` with `payment_type=CARD`; reference no required; no change |
| GCash only | Single `PaymentLine` with `payment_type=GCASH`; reference no required; no change |
| Split (e.g. partial cash + GCash) | Two `PaymentLine` rows; change only on the cash component |
| `amount_tendered` on `SalesTransaction` | Sum of all `PaymentLine.amount` values |
| Change | `max(0, cash_payment_lines_total − remaining_balance)` |

> **Note:** No card terminal integration. Card and GCash payments are entered manually (cashier types in reference/approval number). This keeps the implementation simple and avoids hardware dependencies.

---

## PHASE 5 — Receipt Printing (Dot Matrix)
### Week 2, Days 2–3 | 🟢 GIVE TO CO-DEV

Isolated and testable independently.

### Tasks
- Use `python-escpos` or raw text via `win32print` (Windows) / `lp` (Linux) for dot matrix
- Receipt template: store header, items, totals, cashier name, receipt no, footer
- Print trigger after successful transaction
- Reprint last receipt function (manager only)
- Printer port configurable in Store settings (LPT1, USB, serial)

### Spec to Give Co-Dev
- Receipt layout spec (column widths for 40-col or 80-col dot matrix)
- Printer port config pulled from `Store` model
- `SalesTransaction` + lines data structure from Phase 4

---

## PHASE 6 — Void, Returns & Transaction Management
### Week 2, Days 3–4 | 🔴 YOU handle this

Business logic with audit implications — **keep control.**

### Tasks
- Void transaction (full void only, with manager PIN, within same business day)
- Transaction lookup by receipt number
- Void reverses stock (adds back to `ProductVariant.stock` in local cache)
- Void logged in `AuditLog` model
- "Hold transaction" (park a sale, resume later) — optional but common in shoe retail

---

## PHASE 7 — Reports
### Week 2, Days 4–5 | 🟢 GIVE TO CO-DEV

Data is already there — this is querying and formatting.

### Tasks
- **X-Reading:** current session sales summary (can run anytime, session stays open)
- **Z-Reading:** end of day report, triggers session close
- Daily Sales Report: total sales, voids, discounts, payment breakdown
- Sales by Product / Variant (which sizes/colors sold most)
- Stock on hand report
- All reports: view on screen + print to dot matrix

> **Spec tip:** Give co-dev the Z-reading field list from your original Clarion system as reference. Define exact fields each report needs before he starts.

---

## PHASE 8 — FTP Update Sync
### Week 2 Day 5 – Week 3 Day 1 | 🟢 GIVE TO CO-DEV

Well-isolated, self-contained module.

### Tasks
- FTP client using Python `ftplib` (built-in, no extra install)
- On startup or manual trigger: check FTP server for update package (version file)
- Download and apply: new product data (CSV or JSON) → import to local MySQL
- Price updates, new variants pushed from central server
- Log sync activity with timestamp
- FTP credentials stored in `Store` settings (encrypted with `cryptography` library)

---

## PHASE 8B — Error Handling, Logging & Resilience
### Week 2 Day 5 – Week 3 Day 1 | 🔴 YOU define, 🟢 Co-dev implements

A POS that crashes mid-sale or loses data silently is worse than one that is slow. Define these rules before testing begins.

### Logging Configuration

Set up in `settings/base.py`. Both devs inherit this from day one:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/pos.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {'class': 'logging.StreamHandler'},
    },
    'formatters': {
        'verbose': {'format': '{asctime} {levelname} {module} {message}', 'style': '{'},
    },
    'root': {'handlers': ['file', 'console'], 'level': 'INFO'},
}
```

### Failure Rules by Component

| Component | Failure Scenario | Rule |
|---|---|---|
| Dot matrix printer | Offline / paper out / port error | Catch `Exception` from `win32print`/`escpos` → show "Print failed" dialog with Retry/Skip options. **Sale is already saved — never block a completed transaction on a print failure.** |
| FTP sync | Server unreachable / timeout / bad credentials | Wrap entire sync in `try/except` → write `SyncLog(status='FAILED', error_message=str(e))`. POS continues operating with last known product data. |
| Central DB sync | Partial sync (connection drops mid-run) | Use a database transaction for the upsert batch. Roll back the entire batch on failure. Log the last successfully synced `central_id`. |
| FTP timeout | Hangs indefinitely | Set `ftplib` timeout = value from `Store.ftp_timeout_seconds` (default: 10). Never block the UI thread — run sync in a background thread or Django management command. |
| DB connection loss | `OperationalError` on critical views | Catch on sale save and session views → redirect to `/error/db-offline/` page with a Retry button. Do not catch on read-only report views (let Django's 500 page handle it). |
| Sync during active sale | Sync runs while cashier is mid-transaction | Sync never modifies a `ProductVariant` that appears in an open cart. Check for open `SalesTransaction` with that variant before updating price or deactivating. |

### Startup Health Check

On application startup (in `AppConfig.ready()` or a management command run by the startup script):

```
1. Test MySQL connection → log WARNING if fails, do not block startup
2. Test printer port from Store settings → log WARNING if fails
3. Check for any OPEN POSSessions from a previous day → alert manager on first login
4. Check last sync timestamp → warn if > 24 hours since last successful sync
```

---

## PHASE 9 — Polish, Testing & Deployment
### Week 3, Days 1–3 | 🤝 BOTH

### Tasks
- End-to-end testing: full sale flow with real barcode scanner
- Dot matrix printer alignment tweaks
- Midnight sale scenario testing
- Multi-user concurrent session testing
- Django `collectstatic`, configure for production with `whitenoise`
- Package as standalone: document install steps for local Django server with MySQL
- Backup script for local MySQL database

---

## Coordination Rules for Your Co-Dev

| Rule | Detail |
|---|---|
| **Branch naming** | `feature/phase-2-sessions`, `feature/phase-5-printing` |
| **No direct push to main** | Co-dev submits PR, you review and merge |
| **Daily update** | He sends a short status message each day — done, blocked, next |
| **You define models first** | Never let him create new models without your approval |
| **Spec before code** | Write a 1-page spec (models, inputs, outputs) for each delegated task |
| **Shared `.env.example`** | Keep secrets out of git, share actual `.env` via secure message |

---

## Full Delegation Summary

| Phase | Description | Who | Risk |
|---|---|---|---|
| 1 | Foundation & Core Models | **YOU** | 🔴 High — core schema |
| 2 | Auth & Sessions | Co-dev | 🟢 Low |
| 3A–B | Central DB Mapping & Mirror Models | **YOU** | 🔴 High — data contract |
| 3C–D | Sync Engine & UI | Co-dev | 🟢 Low once spec is done |
| 4 | POS Cashier Frontend | **YOU** | 🔴 High — core UX + logic |
| 5 | Dot Matrix Printing | Co-dev | 🟢 Low |
| 6 | Void & Returns | **YOU** | 🟡 Medium — audit logic |
| 7 | Reports | Co-dev | 🟢 Low |
| 8 | FTP Sync | Co-dev | 🟢 Low |
| 9 | Testing & Deployment | Both | 🤝 — |

---

## Key Libraries

```bash
pip install django mysqlclient python-dotenv pillow
pip install reportlab        # PDF reports as backup/alternative
pip install cryptography     # FTP credential encryption
pip install python-escpos    # Dot matrix / receipt printing
```

---

## Security Checklist

Address each item before go-live. Most are zero-cost Django defaults — they just need to not be disabled.

| Item | Rule |
|---|---|
| `SECRET_KEY` | Generate once with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. Store in `.env` only. Never hardcode or commit. |
| Manager PIN | Store as a hashed value using Django's `make_password()`. Verify with `check_password()`. **Never store or log plain-text PINs.** |
| Session cookies | Set `SESSION_COOKIE_HTTPONLY=True` and `SESSION_COOKIE_SAMESITE='Lax'` in `base.py`. These are Django defaults — just confirm they are not overridden. |
| CSRF protection | Do not disable `django.middleware.csrf.CsrfViewMiddleware`. All POST forms must include `{% csrf_token %}`. If using AJAX, send the CSRF token in the request header. |
| FTP credentials | Encrypt at rest in the `Store` model using `cryptography.fernet`. The encryption key lives in `.env`, not in the database. |
| `DEBUG` in production | Must be `False` in `prod.py`. Django will expose your entire config and traceback to any browser visitor if `DEBUG=True` in production. |
| `ALLOWED_HOSTS` | Set to the machine's actual hostname or IP in `prod.py`. Never use `['*']` in production. |
| Audit log | `AuditLog` table captures: voids, manual discounts above threshold, session open/close, manager PIN use, any price overrides. Fields: `action`, `performed_by (FK User)`, `timestamp`, `affected_object_type`, `affected_object_id`, `old_value`, `new_value`. |
| Role enforcement | Every view uses `@login_required` plus the appropriate role decorator. Hiding a button in the UI is **not** security — the URL must be protected server-side. |
| SQL injection | Use Django ORM for all queries. Never use raw `.raw()` or `cursor.execute()` with string formatting. If raw SQL is ever needed, use parameterized queries only. |
| Backup encryption | If daily DB backups are sent offsite (e.g. FTP or email), encrypt the dump file before sending. A plain `.sql` file contains all customer and sales data. |

---

## Critical Reminders

- The **shoe variant model** (size + color per SKU) defined in Phase 1 is your most important design decision. Get it right before anything else is written.
- The **central DB data contract** in Phase 3 must be finalized before co-dev touches any sync code.
- The POS must always be able to **operate offline** — never depend on a live central DB connection to ring a sale.
- **Midnight sale logic** needs to be tested explicitly — it's easy to get the business date assignment wrong.
