from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from users.models import POSSession


def require_open_session(view_func):
    """
    Ensures the logged-in user is an active member of an open POS session.
    Session is looked up via POSSessionUsers membership, not by store/terminal
    on the user model.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or bool(request.headers.get("HX-Request"))
        )

        user = request.user

        if not user.is_authenticated:
            if is_ajax:
                return JsonResponse({"ok": False, "error": "Please log in to continue."}, status=401)
            return redirect("pos_login")

        session = (
            POSSession.objects.filter(
                session_users__user=user,
                session_users__left_at__isnull=True,
                status=POSSession.STATUS_OPEN,
            )
            .order_by("-opened_at")
            .first()
        )

        if not session:
            if is_ajax:
                return JsonResponse(
                    {"ok": False, "error": "You must open a POS session first."},
                    status=409,
                )
            messages.warning(request, "You must open a POS session first.")
            return redirect("sales:open_session")

        # Attach to request so views can use it without re-querying
        request.pos_session = session

        return view_func(request, *args, **kwargs)

    return wrapper