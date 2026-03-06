"""
URL configuration for users app (POS cashier).
"""

from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path("profile/update/", views.profile_update, name="profile_update"),
    path("profile/suspend-toggle/", views.profile_suspend_toggle, name="profile_suspend_toggle"),
]