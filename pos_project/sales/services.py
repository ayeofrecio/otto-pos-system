"""
Store open/close business logic.

Business-date rule
------------------
The POS operates on a "business date" that does not always match the
calendar date.  Transactions rung after midnight but before cutoff_time
(default 04:00) still belong to the previous business day.

    Wall-clock time       Business date        Can transact?
    ──────────────────    ─────────────────    ─────────────
    09:00 – 23:59         today                Yes
    00:00 – 03:59         yesterday            Yes  (late-night sales)
    04:00 – 08:59         —                    No   (gap window)

Public API
----------
    get_business_date(store_id, now=None)  -> date
    can_open(store_id, terminal_id, now=None) -> bool
    open_store(store_id, terminal_id, user_id, now=None) -> OpenTerminal
    close_store(store_id, terminal_id, business_date) -> int
    assert_store_open(store_id, terminal_id, now=None) -> None
"""

import datetime

from .exceptions import (
    OutsideBusinessHoursError,
    StoreAlreadyOpenError,
    StoreClosedError,
)
from .models import OpenTerminal, TerminalSetup


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_schedule(store_id: str, terminal_id: str) -> tuple[datetime.time, datetime.time]:
    """
    Return (open_time, cutoff_time) for the given store/terminal.
    Falls back to 09:00 / 04:00 if no TerminalSetup row exists.
    """
    try:
        setup = TerminalSetup.objects.get(store_id=store_id, terminal_id=terminal_id)
        return setup.open_time, setup.cutoff_time
    except TerminalSetup.DoesNotExist:
        return datetime.time(9, 0), datetime.time(4, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_business_date(
    store_id: str,
    terminal_id: str,
    now: datetime.datetime | None = None,
) -> datetime.date:
    """
    Return the business date that applies to *now*.

    Transactions before cutoff_time (e.g. 04:00) are attributed to the
    previous calendar day.  Transactions in the gap window (cutoff_time
    to open_time) raise OutsideBusinessHoursError because the store is
    neither open for yesterday's business nor today's.

    Parameters
    ----------
    store_id, terminal_id : str
        Used to look up the store's open_time / cutoff_time from TerminalSetup.
    now : datetime, optional
        Defaults to datetime.datetime.now().  Pass an explicit value for
        testing or when processing back-dated corrections.
    """
    if now is None:
        now = datetime.datetime.now()

    open_time, cutoff_time = _get_schedule(store_id, terminal_id)
    current_time = now.time().replace(second=0, microsecond=0)
    today = now.date()

    # Gap window: after cutoff but before open — store is between days.
    if cutoff_time <= current_time < open_time:
        raise OutsideBusinessHoursError(
            f"Current time {current_time.strftime('%H:%M')} is outside business hours "
            f"(store opens at {open_time.strftime('%H:%M')}, "
            f"cutoff is {cutoff_time.strftime('%H:%M')})."
        )

    # Before cutoff (midnight → 03:59) → still previous business day.
    if current_time < cutoff_time:
        return today - datetime.timedelta(days=1)

    # Normal daytime / evening → today.
    return today


def can_open(
    store_id: str,
    terminal_id: str,
    now: datetime.datetime | None = None,
) -> bool:
    """
    Return True if the store/terminal is eligible to be opened right now.

    Returns False (without raising) when:
      - current time is in the gap window (04:00–08:59)
      - an active OpenTerminal row (tag='') already exists for today's
        business date on this store/terminal
    """
    if now is None:
        now = datetime.datetime.now()

    open_time, cutoff_time = _get_schedule(store_id, terminal_id)
    current_time = now.time().replace(second=0, microsecond=0)

    # Gap window check (no exception — just False).
    if cutoff_time <= current_time < open_time:
        return False

    # Already open check.
    try:
        biz_date = get_business_date(store_id, terminal_id, now)
    except OutsideBusinessHoursError:
        return False

    already_open = OpenTerminal.objects.filter(
        store_id=store_id,
        terminal_id=terminal_id,
        business_date=biz_date,
        tag='',
    ).exists()

    return not already_open


def open_store(
    store_id: str,
    terminal_id: str,
    user_id: str,
    now: datetime.datetime | None = None,
) -> OpenTerminal:
    """
    Open the store for *user_id* on the given store/terminal.

    Creates a new OpenTerminal row with tag='' (open).

    Raises
    ------
    OutsideBusinessHoursError
        If called during the gap window (cutoff_time – open_time).
    StoreAlreadyOpenError
        If an active (tag='') row already exists for this
        store/terminal/business_date/user combination.
    """
    if now is None:
        now = datetime.datetime.now()

    # get_business_date will raise OutsideBusinessHoursError if in gap window.
    biz_date = get_business_date(store_id, terminal_id, now)

    already = OpenTerminal.objects.filter(
        store_id=store_id,
        terminal_id=terminal_id,
        business_date=biz_date,
        user_id=user_id,
        tag='',
    ).first()

    if already is not None:
        raise StoreAlreadyOpenError(
            f"{store_id}/{terminal_id} is already open for {user_id} "
            f"on business date {biz_date}."
        )

    session = OpenTerminal.objects.create(
        store_id=store_id,
        terminal_id=terminal_id,
        business_date=biz_date,
        user_id=user_id,
        tag='',
    )
    return session


def close_store(
    store_id: str,
    terminal_id: str,
    business_date: datetime.date,
) -> int:
    """
    Close all active sessions for *store_id/terminal_id* on *business_date*.

    Marks every OpenTerminal row with tag='' → tag='C'.
    Called as part of the Z-reading / end-of-day close process.

    Returns the number of rows updated (normally 1 per cashier per terminal).
    """
    updated = OpenTerminal.objects.filter(
        store_id=store_id,
        terminal_id=terminal_id,
        business_date=business_date,
        tag='',
    ).update(tag='C')
    return updated


def assert_store_open(
    store_id: str,
    terminal_id: str,
    now: datetime.datetime | None = None,
) -> None:
    """
    Raise StoreClosedError if the store has no active open session right now.

    Call this at the start of any operation that requires the store to be open
    (e.g. ringing a sale, applying a discount, printing an X-reading).

    Raises
    ------
    OutsideBusinessHoursError
        If called during the gap window.
    StoreClosedError
        If no active OpenTerminal row exists for the current business date.
    """
    if now is None:
        now = datetime.datetime.now()

    biz_date = get_business_date(store_id, terminal_id, now)

    is_open = OpenTerminal.objects.filter(
        store_id=store_id,
        terminal_id=terminal_id,
        business_date=biz_date,
        tag='',
    ).exists()

    if not is_open:
        raise StoreClosedError(
            f"{store_id}/{terminal_id} is not open for business date {biz_date}. "
            "Run open_store() before processing transactions."
        )
