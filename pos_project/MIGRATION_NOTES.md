# Migration Notes — Clarion Legacy Models

## Apps Created

| App | Model | Clarion Source | DB Table |
|---|---|---|---|
| `sales` | `TransactionLog` | `TLOG` | `tlog` |
| `sales` | `AccountingSummary` | `ACCT` | `acct` |
| `sales` | `OpenTerminal` | `OPENMMDD` | `openterm` |

Both `TransactionLog` and `AccountingSummary` live in `sales/models.py` — ACCT is daily sales accounting data, not a derived report.

`OpenTerminal` replaces the per-day Clarion file pattern (`OPEN0214`, `OPEN0315` …) with a single table. A `business_date` column carries what the filename used to encode.

## New Files (Store Open/Close Logic)

| File | Purpose |
|---|---|
| `sales/services.py` | `get_business_date()`, `can_open()`, `open_store()`, `close_store()`, `assert_store_open()` |
| `sales/exceptions.py` | `OutsideBusinessHoursError`, `StoreAlreadyOpenError`, `StoreClosedError` |

## Migrations Status

All migrations have been applied to `posdb`.

Migration file: `sales/migrations/0001_initial_clarion_models.py`

To apply to a fresh database:

```bash
python manage.py migrate
```

## Add Apps to INSTALLED_APPS

In `pos_project/settings/base.py`, add both apps:

```python
INSTALLED_APPS = [
    ...
    'sales.apps.SalesConfig',
    'reports.apps.ReportsConfig',  # keep for report views; owns no models
]
```

## Create and Apply Migrations

Once the Django project is set up and MySQL is connected, run:

```bash
python manage.py makemigrations sales
python manage.py makemigrations reports
python manage.py migrate
```

## Import Clarion Data (Phase 0)

After migrations are applied, use `import_clarion.py` to load CSV exports:

```bash
python manage.py import_clarion --source tlog --file path/to/tlog_export.csv
python manage.py import_clarion --source acct --file path/to/acct_export.csv
```

The import script maps each CSV row directly to the corresponding model fields.
Prefix imported `transaction_no` values with `CLR-` to avoid collisions with new transactions.
All imported rows are read-only (do not link to POSSession or apply void logic).

## Payment Type Reference (P01–P24 in AccountingSummary)

The 24 payment buckets correspond to configurable tender types in the Clarion POS.
Map them during import using a lookup against your Clarion tender code table.
Typical mapping example:

| Bucket | Tender |
|---|---|
| P01 | Cash |
| P02 | Credit Card |
| P03 | GCash |
| P04–P24 | Other / unused |
