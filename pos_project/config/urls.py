"""
URL configuration for pos_project.
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

urlpatterns = [
    path("", lambda r: redirect("sales:pos_cashier", permanent=False)),
    path("admin/", admin.site.urls),
    path("pos/", include("sales.urls")),
]
