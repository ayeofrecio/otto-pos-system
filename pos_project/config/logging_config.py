"""
LOGGING dict for the whole project (used by config/settings/base.py).

  logs/app.log   all INFO+ records, rotated daily, 30 days kept
  console        same lines, for the dev server
  ErrorLog table every ERROR+ record (auditlog.handlers.DatabaseErrorHandler)

Business events and data problems are NOT logged here: they go through
auditlog.api.audit() / log_exception() straight into the database.
"""
LINE = '{asctime} {levelname} {name} [{request_id} {user} T{terminal}] {message}'


def build_logging(logs_dir, level='INFO'):
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {'format': LINE, 'style': '{'},
        },
        'filters': {
            'context': {'()': 'auditlog.handlers.ContextFilter'},
            'redact': {'()': 'auditlog.handlers.RedactionFilter'},
            'noise': {'()': 'auditlog.handlers.NoiseFilter'},
        },
        'handlers': {
            'file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'filename': str(logs_dir / 'app.log'),
                'when': 'midnight',
                'backupCount': 30,
                'encoding': 'utf-8',
                'delay': True,
                'formatter': 'standard',
                'filters': ['context', 'redact', 'noise'],
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'filters': ['context', 'redact', 'noise'],
            },
            'db': {
                'class': 'auditlog.handlers.DatabaseErrorHandler',
                'level': 'ERROR',
            },
        },
        'root': {'handlers': ['file', 'console', 'db'], 'level': level},
        'loggers': {
            'django.utils.autoreload': {'level': 'WARNING'},
            'django.db.backends': {'level': 'WARNING'},
        },
    }
