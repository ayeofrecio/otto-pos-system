# Admin User Setup

This guide creates or updates an admin-capable local user for the POS project.

## 1. Ensure Database Is Initialized

Before creating users, complete:

- migrations
- required seed commands

See `DATABASE_FIRST_TIME_SETUP.md`.

## 2. Create or Update Default Admin User

From the project root (folder containing `manage.py`), run:

```powershell
& "D:\Python3\python.exe" manage.py shell -c "from users.models import Users; u, created = Users.objects.get_or_create(username='ariel', defaults={'role':'admin','is_staff':True,'is_superuser':True,'is_active':True}); u.role='admin'; u.is_staff=True; u.is_superuser=True; u.is_active=True; u.set_password('ariel_123!'); u.save(); print('CREATED' if created else 'UPDATED', u.username)"
```

This command is idempotent:

- creates the user if missing
- updates role/flags/password if the user already exists

## 3. Optional: Create Admin Through Django Command

```powershell
& "D:\Python3\python.exe" manage.py createsuperuser
```

If using this method, you can still set POS role explicitly later:

```powershell
& "D:\Python3\python.exe" manage.py shell -c "from users.models import Users; u=Users.objects.get(username='your_admin_username'); u.role='admin'; u.save(); print('ROLE SET TO ADMIN')"
```

## 4. Validate Admin Access

1. Start server:

```powershell
& "D:\Python3\python.exe" manage.py runserver 8000
```

2. Log in using the admin credentials.
3. Confirm user can access protected/admin actions.

## 5. Security Reminder

- Change default passwords in non-local environments.
- Do not commit real production credentials into `.env`.
