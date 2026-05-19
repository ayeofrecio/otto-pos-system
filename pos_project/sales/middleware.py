from datetime import date, datetime, timedelta
from django.http import JsonResponse
from sales.models import TerminalConfiguration
from users.models import POSSession
from django.http import HttpResponse
# Paths that must never be blocked — auth and static
EXEMPT_PATHS = [
    '/pos/login',
    '/pos/logout',
    '/admin/',
    '/pos/to-close-session-details/',
    '/pos/close-session/',
    '/pos/open-session/',
]

# Paths that trigger the Z-reading guard
GUARDED_PREFIX = '/pos/'


class POSGuardMiddleware:
    """
    Blocks POS routes when the terminal's business date is stale
    (i.e. the terminal was opened on a prior day and no Z-reading
    has been performed yet to close that business date).

    Condition: OpenTerminal row exists for this store+terminal
               where business_date < today's calendar date.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # import logging
        # log = logging.getLogger(__name__)
        # log.warning(f"MIDDLEWARE HIT: {request.path} | HTMX: {request.headers.get('HX-Request')} | user: {request.user}")
    
        if self._should_guard(request):
            if self._z_reading_required(request):
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=200)
                    response['HX-Trigger'] = 'openCloseTransModal'
                    return response
                else:
                    # ✅ Never redirect — just flag it and let the view render
                    request.z_reading_required = True

        return self.get_response(request)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_guard(self, request):
        """Return True only for authenticated POS routes we want to guard."""
        if not request.path.startswith(GUARDED_PREFIX):
            return False
        if any(request.path.startswith(p) for p in EXEMPT_PATHS):
            return False
        if not request.user.is_authenticated:
            return False
        
        return True

    def _z_reading_required(self, request):
        """
        Returns True if the active POSSession for this store+terminal
        has passed its cutoff deadline.

        Deadline = (business_date + 1 day) at cutoff_time
        Example:  business_date=2026-04-26, cutoff_time=04:00
                → deadline = 2026-04-27 04:00
                → if now > deadline, Z-reading is required
        """
        store_id, terminal_id = self._get_terminal_ids(request)
        if not store_id or not terminal_id:
            return False
        # print(f"POSGuardMiddleware: Checking Z-reading requirement for store={store_id} terminal={terminal_id}")
        try:
            # 1. Get the terminal config for cutoff_time
            config = TerminalConfiguration.objects.filter(
                store_id=store_id,
                terminal_id=terminal_id,
            ).first()

            if not config:
                return False

            # 2. Get the currently open session for this terminal
            session = POSSession.objects.filter(
                store_id=store_id,
                terminal_id=terminal_id,
                status=POSSession.STATUS_OPEN,
            ).order_by('-opened_at').first()
            # print(f"POSGuardMiddleware: Found session: {session.opened_at if session else 'None'} with business_date={session.business_date if session else 'N/A'}")
            if not session:
                return False  # no open session, nothing to guard

            # 3. Compute the deadline:
            #    cutoff_time belongs to the NEXT calendar day after business_date
            #    e.g. business_date=2026-04-26, cutoff=04:00
            #         → deadline = 2026-04-27 04:00:00
            next_day = session.business_date + timedelta(days=1)
            deadline = datetime.combine(next_day, config.cutoff_time)
            # print(f"POSGuardMiddleware: store={store_id} terminal={terminal_id} session_date={session.business_date} cutoff={config.cutoff_time} deadline={deadline}")
            # 4. If we are past that deadline, Z-reading is required
            # print(f"POSGuardMiddleware: Now: {datetime.now()}, Deadline: {deadline}, Past deadline: {datetime.now() > deadline}")
            now = datetime.now()
            return now > deadline

        except Exception:
            return False  # fail open — never lock cashiers out on DB error

    def _get_terminal_ids(self, request):
        """
        Pull store_id and terminal_id from the session.
        Falls back to the hardcoded constants that views.py currently uses.

        TODO: Once store/terminal are properly stored in the session
              (or on the user profile), remove the fallback constants.
        """
        # TODO: replace fallback once STORE_ID/TERMINAL_ID move to session
        STORE_ID_FALLBACK = '001'
        TERMINAL_ID_FALLBACK = '001'

        store_id = request.session.get('store_id', STORE_ID_FALLBACK)
        terminal_id = request.session.get('terminal_id', TERMINAL_ID_FALLBACK)
        return store_id, terminal_id