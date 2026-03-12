"""
URL configuration for pos_project.
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

from users import views as user_views

urlpatterns = [
    path("", lambda r: redirect("sales:pos_cashier", permanent=False)),
    path("admin/", admin.site.urls),
    path("pos/", include("sales.urls")),
    path("users/", include("users.urls")),
    path("login/", user_views.pos_login, name="pos_login"),
    path("logout/", user_views.pos_logout, name="pos_logout"),
]
