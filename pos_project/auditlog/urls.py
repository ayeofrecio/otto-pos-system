from django.urls import path

from . import views

app_name = 'auditlog'

urlpatterns = [
    path('audit/', views.audit_list, name='audit_list'),
    path('errors/', views.error_list, name='error_list'),
    path('health/', views.health, name='health'),
    path('transaction-status/<str:trans_no>/', views.transaction_status, name='transaction_status'),
    path('client-event/', views.client_event, name='client_event'),
    path('errors/<int:pk>/review/', views.error_review, name='error_review'),
]
