from django.urls import path
from .views import series_report


urlpatterns = [
    # path('', home, name='home'),
    path("series/", series_report, name="series_report"),
]