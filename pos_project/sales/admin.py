from django.contrib import admin

from .models import (
    AccountingSummary,
    Color,
    Item,
    ItemDetail,
    ItemLink,
    OpenTerminal,
    POSFunction,
    POSTransCounter,
    POSTransNumber,
    Size,
    SuspendedTransaction,
    Tender,
    TempTransaction,
    TerminalSetup,
    TransactionHeader,
    TransactionItem,
    Payment,
)


@admin.register(TransactionHeader)
class TransactionHeaderAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_no', 'transaction_date', 'transaction_time',
        'transaction_type', 'store_id', 'terminal_id', 'user_id',
        'item_count', 'total_amount',
    )
    list_filter = ('store_id', 'terminal_id', 'transaction_type', 'transaction_date')
    search_fields = ('transaction_no', 'user_id', 'table_id', 'served_by')
    date_hierarchy = 'transaction_date'
    ordering = ('-transaction_date', 'transaction_no')
    readonly_fields = [f.name for f in TransactionHeader._meta.get_fields()
                       if not f.is_relation]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('items', 'payments')

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description='Total')
    def total_amount(self, obj):
        total = sum(p.amount for p in obj.payments.all())
        return f'{total:,.2f}'


@admin.register(TransactionItem)
class TransactionItemAdmin(admin.ModelAdmin):
    list_display = (
        'header', 'item_code', 'item_description',
        'item_qty', 'item_uom', 'item_price',
        'item_discount', 'item_price_ext',
    )
    list_filter = ('item_department', 'item_class', 'item_type')
    search_fields = ('item_code', 'item_description', 'header__transaction_no')
    ordering = ('header__transaction_date', 'header__transaction_no')
    readonly_fields = [f.name for f in TransactionItem._meta.get_fields()
                       if not f.is_relation]
    raw_id_fields = ('header',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'header', 'pcode', 'tender_desc', 'amount', 'payment_reference',
    )
    list_filter = ('pcode',)
    search_fields = ('header__transaction_no', 'pcode', 'payment_reference')
    ordering = ('header__transaction_date',)
    readonly_fields = [f.name for f in Payment._meta.get_fields()
                       if not f.is_relation]
    raw_id_fields = ('header',)


@admin.register(AccountingSummary)
class AccountingSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'store_id', 'terminal_id', 'transaction_date', 'user_id',
        'items_sold', 'customer_count', 'first_trans_no', 'last_trans_no',
        'x_reading', 'z_reading', 'old_total', 'new_total', 'non_vat', 'vatable',
    )
    list_filter = ('store_id', 'terminal_id', 'transaction_date')
    search_fields = ('user_id', 'store_id', 'terminal_id', 'first_trans_no', 'last_trans_no')
    date_hierarchy = 'transaction_date'
    ordering = ('-transaction_date', 'store_id', 'terminal_id')
    readonly_fields = [f.name for f in AccountingSummary._meta.get_fields()]


@admin.register(TerminalSetup)
class TerminalSetupAdmin(admin.ModelAdmin):
    list_display = ('store_id', 'terminal_id', 'print_port', 'draw_port', 'disp_port', 'vat')
    search_fields = ('store_id', 'terminal_id')


@admin.register(TempTransaction)
class TempTransactionAdmin(admin.ModelAdmin):
    """
    Django admin configuration for TempTransaction model.

    This admin class customizes the Django admin interface for managing temporary
    transaction records in the POS system.

    Attributes:
        list_display (tuple): Fields displayed in the admin list view including
            transaction number, date, store and terminal identifiers, user ID,
            and item details (code, description, quantity, extended price).
        
        list_filter (tuple): Enables filtering by store_id and terminal_id in
            the admin sidebar for easier transaction lookup by location.
        
        search_fields (tuple): Enables full-text search functionality for
            transaction_no, item_code, and user_id fields in the admin interface.
    """
    list_display = (
        'transaction_no', 'transaction_date', 'store_id', 'terminal_id',
        'user_id', 'item_code', 'item_description', 'item_qty', 'item_price_ext',
    )
    list_filter = ('store_id', 'terminal_id')
    search_fields = ('transaction_no', 'item_code', 'user_id')


# @admin.register(ClarionUser)
# class ClarionUserAdmin(admin.ModelAdmin):
#     list_display = (
#         'user_id', 'last_name', 'first_name', 'user_level',
#         'user_group', 'department', 'active', 'suspended',
#     )
#     list_filter = ('user_group', 'department', 'active', 'suspended', 'user_level')
#     search_fields = ('user_id', 'last_name', 'first_name', 'long_name')
#     ordering = ('last_name', 'first_name')


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = (
        'pcode', 'key_name', 'description', 'pallow', 'pchange',
        'pdocment', 'pmarkup', 'pmarkamt',
    )
    search_fields = ('pcode', 'description', 'key_name')


@admin.register(SuspendedTransaction)
class SuspendedTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_no', 'transaction_date', 'store_id', 'terminal_id',
        'user_id', 'table_id', 'item_code', 'item_description', 'item_qty',
    )
    list_filter = ('store_id', 'terminal_id')
    search_fields = ('transaction_no', 'item_code', 'user_id', 'table_id')


@admin.register(POSTransCounter)
class POSTransCounterAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_no')


@admin.register(POSTransNumber)
class POSTransNumberAdmin(admin.ModelAdmin):
    list_display = ('transaction_no', 'grand_tot', 'grand_tot2', 'prev_ctr', 'curr_ctr')


@admin.register(OpenTerminal)
class OpenTerminalAdmin(admin.ModelAdmin):
    list_display = ('store_id', 'terminal_id', 'user_id', 'tag')
    list_filter = ('store_id', 'terminal_id')
    search_fields = ('user_id',)


@admin.register(POSFunction)
class POSFunctionAdmin(admin.ModelAdmin):
    list_display = ('code', 'desc', 'key_code')
    search_fields = ('code', 'desc')


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('code', 'color', 'set_value', 'multi')
    search_fields = ('code', 'color')


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('code', 'size', 'set_value')
    search_fields = ('code', 'size')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        'icode', 'short_desc', 'department', 'item_class', 'color', 'size',
        'price', 'cost', 'stocks', 'inactive',
    )
    list_filter = ('department', 'item_class', 'inactive', 'item_type', 'tax_code')
    search_fields = ('icode', 'icode2', 'icode3', 'short_desc', 'long_desc', 'supplier')
    ordering = ('icode',)


@admin.register(ItemDetail)
class ItemDetailAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'icode', 'color', 'size', 'price', 'cost', 'stocks1')
    list_filter = ('color', 'size')
    search_fields = ('barcode', 'icode')
    ordering = ('icode', 'color', 'size')


@admin.register(ItemLink)
class ItemLinkAdmin(admin.ModelAdmin):
    list_display = ('icode', 'link_code', 'desc', 'price', 'price2')
    search_fields = ('icode', 'link_code', 'desc')
