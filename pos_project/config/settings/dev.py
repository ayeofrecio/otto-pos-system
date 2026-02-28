"""
Development settings.
Used by both developers locally.  Never used in production.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

# In dev you can override the DB to SQLite for quick tests without MySQL:
#   set DB_ENGINE=django.db.backends.sqlite3 in your .env
#   and DB_NAME to a file path, e.g. DB_NAME=posdb.sqlite3
import os
if os.environ.get('DB_ENGINE'):
    DATABASES['default']['ENGINE'] = os.environ['DB_ENGINE']
    if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
        DATABASES['default'].pop('OPTIONS', None)
        DATABASES['default'].pop('USER', None)
        DATABASES['default'].pop('PASSWORD', None)
        DATABASES['default'].pop('HOST', None)
        DATABASES['default'].pop('PORT', None)

# Shorter cache for static files in dev
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
