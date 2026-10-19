"""
Settings for the auditlog app. Override any key with an AUDITLOG dict in
settings (see config/settings/base.py); everything else uses these defaults.
"""
from django.conf import settings

DEFAULTS = {
    'enabled': True,                   # False = audit()/log_exception() do nothing
    'slow_request_seconds': 2.0,       # requests slower than this are logged as warnings
    'dedup_window_seconds': 3600,      # identical exceptions within this window bump `count`
    'breaker_seconds': 30,             # after a failed DB write, use the file for this long
    'fallback_file': 'pending_db_logs.jsonl',   # inside settings.LOGS_DIR
    'default_terminal': '001',         # same fallback sales.middleware uses
    'redact_keys': ('pin', 'password', 'card', 'card_no', 'card_number', 'cvv'),
    'audit_retention_days': 730,
    'error_retention_days': 90,
}


def get(name):
    return {**DEFAULTS, **getattr(settings, 'AUDITLOG', {})}[name]
