from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from users.models import POSSession


def require_open_session(view_func):
    """
    Ensures the logged-in user has an OPEN POS session
    before accessing POS views.
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

        # # get Users profile
        # profile = getattr(user, "profile", None)

        # if not profile:
        #     messages.error(request, "User profile not found.")
        #     return redirect("pos_login")

        # if profile.is_suspended:
        #     messages.error(request, "Your account is suspended.")
        #     return redirect("pos_login")

        # check open session
        session = POSSession.objects.filter(
            cashier=user,
            status="open"
        ).first()

        if not session:
            if is_ajax:
                return JsonResponse(
                    {"ok": False, "error": "You must open a POS session first."},
                    status=409,
                )
            messages.warning(request, "You must open a POS session first.")
            return redirect("sales:open_session")

        # attach objects to request for easy access
        request.pos_session = session
        request.user_profile = user

        return view_func(request, *args, **kwargs)

    return wrapper