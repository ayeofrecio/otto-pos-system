# POS Migration — Current Status & Plan Summary

## What You Can Run Today

### 1. Django Admin — Fully Functional

Start the development server and access the admin panel:

```bash
cd pos_project
python manage.py createsuperuser   # if you haven't already
python manage.py runserver
```

Open **http://127.0.0.1:8000/admin/** in your browser.

**16 models** are registered and browsable:

| Section | Models |
|---|---|
| **Sales** | TransactionLog, AccountingSummary |
| **Config** | TerminalSetup, Tender, POSFunction |
| **Users** | ClarionUser |
| **Cart** | TempTransaction, SuspendedTransaction |
| **Counters** | POSTransCounter, POSTransNumber |
| **Sessions** | OpenTerminal |
| **Inventory** | Item, ItemDetail, ItemLink, Color, Size |

All have search fields, list filters, and column displays configured in `sales/admin.py`.

---

### 2. MySQL Database — Live and Migrated

- **Database:** `posdb`
- **Connection:** Host `127.0.0.1`, Port `3306`, User `root`, Password in `.env`
- **Tables created:** `tlog`, `acct`, `setup`, `temptrans`, `users`, `tenders`, `suspend`, `posnctr`, `posnbr`, `openterm`, `functions`, `colors`, `sizes`, `items`, `itemdtl`, `itemlink` (plus Django auth/admin/sessions tables)

Connect with MySQL Workbench, DBeaver, HeidiSQL, or any MySQL client.

---

### 3. Import Command — Ready for Clarion CSV Exports

Once you export your Clarion data to CSV:

```bash
# Dry-run first (validate without writing)
python manage.py import_clarion --source tlog --file path/to/tlog.csv --dry-run

# Real import
python manage.py import_clarion --source tlog --file path/to/tlog.csv
python manage.py import_clarion --source acct --file path/to/acct.csv
```

- Prefixes `transaction_no` with `CLR-` automatically
- Skips duplicates on re-run
- Supports `--batch-size` and `--encoding` options

---

### 4. Store Open/Close Logic — Ready to Call

The service layer is implemented and ready for Phase 2 views:

```python
from sales.services import get_business_date, open_store, close_store, assert_store_open
from sales.exceptions import OutsideBusinessHoursError, StoreAlreadyOpenError, StoreClosedError
```

- **9am open** / **4am cutoff** (late-night sales belong to previous business day)
- `tag=''` = open, `tag='C'` = closed
- Configurable per terminal via `TerminalSetup.open_time` and `cutoff_time`

---

### 5. Project Structure

```
pos_project/
├── manage.py
├── .env
├── config/                 # Django project package (renamed from pos_project)
│   ├── settings/           # base.py, dev.py, prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── sales/
│   ├── models.py           # 16 Clarion models
│   ├── admin.py
│   ├── services.py        # Store open/close logic
│   ├── exceptions.py
│   └── management/commands/import_clarion.py
├── reports/
├── static/
└── templates/
```

---

## What You Cannot See Yet

| Missing | Phase | Description |
|---|---|---|
| **Cashier login screen** | 2 | No login/logout views; no POS-facing URL |
| **POS cashier frontend** | 4 | No product search, cart, payment screen |
| **Receipt printing** | 5 | No dot matrix output |
| **Void / returns** | 6 | No transaction lookup or void flow |
| **X-Reading / Z-Reading** | 7 | No reports |
| **FTP sync** | 8 | No product sync from central |
| **Root URL** | — | `http://127.0.0.1:8000/` shows Django default page; only `/admin/` is configured |

**Next visible milestone:** Phase 2 — cashier login screen and session management.

---

## POS Migration Plan — Full Summary

### Project Overview

| Detail | Info |
|---|---|
| **Timeline** | 2–3 weeks |
| **Stack** | Django + MySQL + Django REST Framework |
| **Team** | You (lead) + 1 remote co-developer |
| **POS Type** | Standalone with FTP-based updates |
| **Hardware** | Dot matrix printer, barcode scanner |
| **Domain** | Shoe retail (SKU + size + color variants) |

---

### Phase 0 — Legacy Clarion Data Extraction & Migration ✅ (Mostly Done)

**Status:** Django scaffold, models, migrations, and import script are in place. Manual CSV export from Clarion still required.

**Tasks:**
- Audit Clarion database
- Export product catalog and transaction history to CSV
- Build Clarion → Django field mapping
- Write `import_clarion.py` ✅
- Frozen history rule: imported rows are read-only, prefixed with `CLR-`

**Deliverable:** CSV exports, tested import, documented record counts.

---

### Phase 1 — Foundation & Core Models ✅ (Clarion Models Done)

**Status:** Clarion-equivalent models (Item, ItemDetail, Color, Size, etc.) exist. Phase 1 *Product/ProductVariant* schema from the plan will be refined when moving to the new product model.

**Tasks:**
- Django project setup ✅
- MySQL connection ✅
- Core models (Clarion legacy + future Product/ProductVariant)
- Django admin registration ✅
- Migrations run ✅

---

### Phase 2 — User Auth & Session Management

**Owner:** Co-dev (low risk)

**Tasks:**
- Login/logout views (Django session-based)
- User roles and decorators (`@cashier_required`, `@manager_required`)
- `POSSession` model (opened_by, business_date, status)
- Midnight sale logic (00:00–04:00 → previous business day)
- Force open session before sale
- Close session (Z-reading) with manager PIN

---

### Phase 3 — Central Database Integration & Local Sync

**Owner:** You define schema; Co-dev builds engine

**Tasks:**
- Map central DB schema to Django models
- Add `central_id`, `last_synced_at` to ProductVariant
- Sync engine: pull, upsert, soft-deactivate
- Manual "Sync Now" button, auto-sync on startup
- Conflict rules: central system always wins

---

### Phase 4 — POS Cashier Frontend (Core Sales)

**Owner:** You (high risk — core UX)

**Tasks:**
- Cashier screen: product search, cart, totals
- Barcode scanner input handling
- Shoe variant selector (size/color popup)
- Add to cart, qty, remove, discounts
- Payment screen: cash, card, GCash, split payments
- `SalesTransaction` + `SalesTransactionLine` + `PaymentLine`
- Receipt number generation

---

### Phase 5 — Receipt Printing (Dot Matrix)

**Owner:** Co-dev (low risk)

**Tasks:**
- `python-escpos` or `win32print` / `lp`
- Receipt template: header, items, totals, footer
- Print on successful transaction
- Reprint last receipt (manager only)
- Printer port from Store settings

---

### Phase 6 — Void, Returns & Transaction Management

**Owner:** You (medium risk — audit logic)

**Tasks:**
- Full void with manager PIN (same business day)
- Transaction lookup by receipt number
- Void reverses stock
- Void logged in `AuditLog`
- Optional: hold/park transaction

---

### Phase 7 — Reports

**Owner:** Co-dev (low risk)

**Tasks:**
- X-Reading (session summary)
- Z-Reading (end of day, triggers close)
- Daily Sales Report
- Sales by Product/Variant
- Stock on hand
- View on screen + print to dot matrix

---

### Phase 8 — FTP Update Sync

**Owner:** Co-dev (low risk)

**Tasks:**
- FTP client (`ftplib`)
- Check for update package on startup/manual trigger
- Download product data (CSV/JSON)
- Encrypt FTP credentials in Store settings

---

### Phase 8B — Error Handling, Logging & Resilience

**Owner:** You define rules; Co-dev implements

**Tasks:**
- Logging config in `base.py`
- Failure rules: printer, FTP, DB, sync conflicts
- Startup health check (MySQL, printer, open sessions, last sync)

---

### Phase 9 — Polish, Testing & Deployment

**Owner:** Both

**Tasks:**
- End-to-end testing with barcode scanner
- Midnight sale scenario testing
- `collectstatic`, WhiteNoise for production
- Install docs, backup script

---

### Delegation Summary

| Phase | Description | Who | Risk |
|---|---|---|---|
| 0 | Legacy Data Extraction | **YOU** | — |
| 1 | Foundation & Core Models | **YOU** | 🔴 High |
| 2 | Auth & Sessions | Co-dev | 🟢 Low |
| 3A–B | Central DB Mapping & Mirror Models | **YOU** | 🔴 High |
| 3C–D | Sync Engine & UI | Co-dev | 🟢 Low |
| 4 | POS Cashier Frontend | **YOU** | 🔴 High |
| 5 | Dot Matrix Printing | Co-dev | 🟢 Low |
| 6 | Void & Returns | **YOU** | 🟡 Medium |
| 7 | Reports | Co-dev | 🟢 Low |
| 8 | FTP Sync | Co-dev | 🟢 Low |
| 9 | Testing & Deployment | Both | — |

---

### Critical Reminders

- **Shoe variant model** (size + color per SKU) is the most important design decision.
- **Central DB data contract** must be finalized before sync code is written.
- POS must **operate offline** — never depend on live central DB to ring a sale.
- **Midnight sale logic** (9am open, 4am cutoff) must be tested explicitly.
