"""
URL configuration for users app (POS cashier).
"""

from django.urls import path

from . import views
from .decorators import cashier_required, supervisor_required, manager_required, admin_required

app_name = "users"

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    # path("profile/", cashier_required(views.profile_view), name="profile"),
    path("profile/update/", cashier_required(views.profile_update), name="profile_update"),
    path("profile/suspend-toggle/", manager_required(views.profile_suspend_toggle), name="profile_suspend_toggle"),
]