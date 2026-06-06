"""
URL configuration for sales app (POS cashier).
"""

from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.cashier_view, name="pos_cashier"),
    path("admin/posnbr-init/", views.admin_posnbr_init, name="admin_posnbr_init"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/variants/", views.item_variants, name="item_variants"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("cart/line-disc/", views.cart_line_disc, name="cart_line_disc"),
    path("cart/line-price-override/", views.cart_line_price_override, name="cart_line_price_override"),
    path("cart/trans-disc/", views.cart_trans_disc, name="cart_trans_disc"),
    path("cart/new/", views.cart_new, name="cart_new"),
    path("cart/suspend/", views.cart_suspend, name="cart_suspend"),
    path("cart/suspended-list/", views.cart_suspended_list, name="cart_suspended_list"),
    path("cart/suspended-retrieve/", views.cart_suspended_retrieve, name="cart_suspended_retrieve"),
    path("cart/item-return-toggle/", views.cart_item_return_toggle, name="cart_item_return_toggle"),
    path("cart/return-lookup/", views.cart_return_lookup, name="cart_return_lookup"),
    path("cart/return-import/", views.cart_return_import, name="cart_return_import"),
    path("cart/void-item/", views.cart_void_item, name="cart_void_item"),
    path("cart/void-transaction/", views.cart_void_transaction, name="cart_void_transaction"),
    path("cart/void-previous/", views.cart_void_previous, name="cart_void_previous"),
    path("pay/", views.pay_view, name="pay"),
    path("pay/complete/", views.payment_complete, name="payment_complete"),
    path("receipt/", views.receipt_view, name="receipt"),
    path("journal/", views.transaction_journal, name="transaction_journal"),
    path("item-search/", views.item_search, name="item_search"),
    path("open-session/", views.open_session, name="open_session"),
    path("close-session/", views.close_session, name="close_session"),
    path("to-close-session-details/", views.to_close_session_details, name="to_close_session_details"),
    path('debug-json/', views.debug_sessions_json, name='debug_sessions_json'),
    path("z-reading/", views.z_reading_view, name="z_reading"),
    path("x-reading/", views.print_x_reading, name="x_reading"),
    path("update-from-csv/", views.update_from_csv, name="update_from_csv"),
]
