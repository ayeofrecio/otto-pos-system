from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie

from sales.views import _get_store_name

# Create your views here.


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
def pos_login(request):
    """Cashier login page."""
    if request.user.is_authenticated:
        return redirect("sales:pos_cashier")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "") 
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                next_url = request.GET.get("next") or "sales:pos_cashier"
                return redirect(next_url)
        return render(request, "users/login.html", {"error": "Invalid username or password.", "store_name": _get_store_name()})

    return render(request, "users/login.html", {"store_name": _get_store_name()})


def pos_logout(request):
    """Cashier logout."""
    logout(request)
    return redirect("pos_login")


@ensure_csrf_cookie
def profile_view(request):
    """View cashier profile."""
    if not request.user.is_authenticated:
        return redirect("sales:pos_login")
    return render(request, "users/profile.html", {"store_name": _get_store_name()})


@ensure_csrf_cookie
def profile_update(request):
    """Update cashier profile."""
    if not request.user.is_authenticated:
        return redirect("sales:pos_login")
    # For simplicity, we won't implement actual update logic here.
    return render(request, "users/profile_update.html", {"store_name": _get_store_name()})

@ensure_csrf_cookie
def profile_suspend_toggle(request):
    """Toggle cashier account suspension."""
    if not request.user.is_authenticated:
        return redirect("sales:pos_login")
    # For simplicity, we won't implement actual suspend logic here.
    return render(request, "users/profile_suspend_toggle.html", {"store_name": _get_store_name()})

