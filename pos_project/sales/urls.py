"""
URL configuration for sales app (POS cashier).
"""

from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.cashier_view, name="pos_cashier"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("cart/line-disc/", views.cart_line_disc, name="cart_line_disc"),
    path("cart/trans-disc/", views.cart_trans_disc, name="cart_trans_disc"),
    path("cart/new/", views.cart_new, name="cart_new"),
    path("pay/", views.pay_view, name="pay"),
    path("pay/complete/", views.payment_complete, name="payment_complete"),
    path("receipt/", views.receipt_view, name="receipt"),
    path("item-search/", views.item_search, name="item_search"),
    path("open-session/", views.open_session, name="open_session"),
    path("close-session/", views.close_session, name="close_session"),
    path("to-close-session-details/", views.to_close_session_details, name="to_close_session_details"),
    path('debug-json/', views.debug_sessions_json, name='debug_sessions_json'),
    path("z-reading/", views.z_reading_view, name="z_reading"),
    path("x-reading/", views.print_x_reading, name="x_reading"),
]
