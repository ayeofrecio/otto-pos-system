"""
Every audit action, exception kind and exception code lives here.

To add a new event: add one line to the right enum, then call
`audit(Action.X, ...)` or `log_exception(Kind.X, Code.Y, ...)`.

These enums are deliberately NOT used as model `choices=`, so adding a value
never needs a database migration. Old rows keep working if a value is removed.
"""
from django.db.models import TextChoices


class Action(TextChoices):
    """Business events written to AuditLog."""
    LOGIN_OK = 'LOGIN_OK'
    LOGIN_FAIL = 'LOGIN_FAIL'
    LOGOUT = 'LOGOUT'
    MANAGER_PIN_OK = 'MANAGER_PIN_OK'
    MANAGER_PIN_FAIL = 'MANAGER_PIN_FAIL'
    VOID_ITEM = 'VOID_ITEM'
    VOID_TRANS = 'VOID_TRANS'
    VOID_PREVIOUS = 'VOID_PREVIOUS'
    RETURN_ITEM = 'RETURN_ITEM'
    LINE_DISC = 'LINE_DISC'
    TRANS_DISC = 'TRANS_DISC'
    PRICE_OVERRIDE = 'PRICE_OVERRIDE'
    TRANS_SUSPEND = 'TRANS_SUSPEND'
    TRANS_RESUME = 'TRANS_RESUME'
    PAYMENT_COMPLETE = 'PAYMENT_COMPLETE'
    CASH_IN = 'CASH_IN'
    CASH_OUT = 'CASH_OUT'
    SESSION_OPEN = 'SESSION_OPEN'
    SESSION_CLOSE = 'SESSION_CLOSE'
    X_READ = 'X_READ'
    Z_READ = 'Z_READ'
    CONNECTION_LOST = 'CONNECTION_LOST'
    CONNECTION_RESTORED = 'CONNECTION_RESTORED'


class Kind(TextChoices):
    """Category of an exception row (ErrorLog.kind)."""
    SYSTEM = 'SYSTEM'          # unexpected crash / unhandled exception
    DATA = 'DATA'              # bad or missing data (item, price, totals)
    VALIDATION = 'VALIDATION'  # input rejected
    DEVICE = 'DEVICE'          # printer, cash drawer
    CONNECTION = 'CONNECTION'  # network / database unreachable
    IMPORT = 'IMPORT'          # CSV / Clarion import rejects


class Code(TextChoices):
    """Stable short code identifying the problem (ErrorLog.code)."""
    UNHANDLED = 'UNHANDLED'
    ITEM_NOT_FOUND = 'ITEM_NOT_FOUND'
    PRICE_MISSING = 'PRICE_MISSING'
    BARCODE_INVALID = 'BARCODE_INVALID'
    TOTAL_MISMATCH = 'TOTAL_MISMATCH'
    TXN_LOG_FAILED = 'TXN_LOG_FAILED'
    RETURN_INVALID = 'RETURN_INVALID'
    BIZDATE_FALLBACK = 'BIZDATE_FALLBACK'
    IMPORT_ROW_REJECTED = 'IMPORT_ROW_REJECTED'
    PRINTER_FAIL = 'PRINTER_FAIL'
    DRAWER_FAIL = 'DRAWER_FAIL'
    ZREAD_UPDATE_FAILED = 'ZREAD_UPDATE_FAILED'
    DB_UNAVAILABLE = 'DB_UNAVAILABLE'


class Status(TextChoices):
    """Review state of an exception row (ErrorLog.status)."""
    NEW = 'NEW'
    REVIEWED = 'REVIEWED'
    RESOLVED = 'RESOLVED'
