"""
Custom exceptions for POS store open/close business logic.
"""


class OutsideBusinessHoursError(Exception):
    """
    Raised when a cashier attempts to open the store during the gap window
    between cutoff_time (04:00) and open_time (09:00).
    No transactions or logins are permitted in this window.
    """


class StoreAlreadyOpenError(Exception):
    """
    Raised when open_store() is called but an active OpenTerminal row
    (tag='') already exists for the same store/terminal/business_date/user.
    """


class StoreClosedError(Exception):
    """
    Raised when a cashier tries to ring a sale but the store has no active
    OpenTerminal row (tag='') for the current business date, meaning the
    store has not been opened yet or has already been Z-read / closed.
    """
