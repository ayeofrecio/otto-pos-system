from django.contrib import admin
from sales.models import POSFunction
from .forms import PosFunctionForm


admin.site.unregister(POSFunction)      # ← removes the sales registration first


@admin.register(POSFunction)
class PosFunctionAdmin(admin.ModelAdmin):
    form = PosFunctionForm
    list_display = ('code', 'desc', 'keycode_display')
    search_fields = ('code', 'desc')
    ordering = ('code',)

    def keycode_display(self, obj):
        return obj.key_code.strip() if obj.key_code else '—'
    keycode_display.short_description = 'Key'