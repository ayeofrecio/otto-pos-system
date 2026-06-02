# First-Time Database Setup

This guide initializes a brand-new local database for the POS project.

## Prerequisites

- Python installed (project currently uses `D:\Python3\python.exe`)
- MySQL Server installed
- MySQL root access
- Project dependencies installed

## 1. Configure Environment

Update project environment variables in `.env` (same folder as `manage.py`):

```env
SECRET_KEY=your_secret_key
DJANGO_SETTINGS_MODULE=config.settings.dev

DB_NAME=posdb
DB_USER=root
DB_PASSWORD=your_mysql_root_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

## 2. Create the Database

If `mysql` is on PATH:

```powershell
mysql -u root -pyour_mysql_root_password -e "DROP DATABASE IF EXISTS posdb; CREATE DATABASE posdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

If `mysql` is not on PATH (example default location):

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root "-pyour_mysql_root_password" -e "DROP DATABASE IF EXISTS posdb; CREATE DATABASE posdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## 3. Run Migrations

From the project root (folder containing `manage.py`):

```powershell
& "D:\Python3\python.exe" manage.py migrate
```

## 4. Seed Required POS Data

Run in this order:

```powershell
& "D:\Python3\python.exe" manage.py seed_store
& "D:\Python3\python.exe" manage.py seed_tenders
& "D:\Python3\python.exe" manage.py seed_settings
& "D:\Python3\python.exe" manage.py init_posnbr --start 00000001 --force
& "D:\Python3\python.exe" manage.py seed_color_size_items
& "D:\Python3\python.exe" manage.py seed_sample_items
```

Optional sample data variant:

```powershell
& "D:\Python3\python.exe" manage.py sample_actual_items
```

## 5. Verify Project Health

```powershell
& "D:\Python3\python.exe" manage.py check
```

Expected result:

- `System check identified no issues (0 silenced).`

## 6. Run the Application

```powershell
& "D:\Python3\python.exe" manage.py runserver 8000
```

## Notes for Separate Branch Databases

For another local clone (example `testing-updated-merge`), set a different `DB_NAME` such as `posdb_testing` and repeat the same steps. This keeps data isolated between branches.
