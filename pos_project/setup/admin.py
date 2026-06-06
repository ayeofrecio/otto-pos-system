from django.contrib import admin
from django.utils.html import format_html

from sales.models import POSFunction
from .forms import PosFunctionForm


CHAR_TO_FKEY = {
    chr(0xDC): 'F1',
    chr(0xD8): 'F2',
    chr(0xE9): 'F3',
    chr(0xF7): 'F4',
    chr(0xF8): 'F5',
    chr(0xF9): 'F6',
    chr(0xFA): 'F7',
    chr(0xFB): 'F8',
    chr(0xFC): 'F9',
    chr(0xFD): 'F10',
    chr(0xFE): 'F11',
    chr(0xFF): 'F12',
}

SPECIAL_KEY_MAP = {
    'CR': 'Enter',
    'EC': 'Esc',
    'IC': 'Ins',
    'DL': 'Del',
    'HM': 'Home',
    'ND': 'End',
    'PU': 'PgUp',
    'PD': 'PgDn',
    'AU': '↑',
    'AD': '↓',
    'AL': '←',
    'AR': '→',
    'BK': 'Bksp',
    'TB': 'Tab',
}


admin.site.unregister(POSFunction)      # ← removes the sales registration first


@admin.register(POSFunction)
class PosFunctionAdmin(admin.ModelAdmin):
    form = PosFunctionForm
    list_display = ('code', 'desc', 'assigned_key', 'edit_link')
    list_display_links = ('code',)
    search_fields = ('code', 'desc')
    ordering = ('code',)

    def assigned_key(self, obj):
        raw_value = (obj.key_code or '').strip()
        if not raw_value:
            return '—'
        if raw_value in CHAR_TO_FKEY:
            return CHAR_TO_FKEY[raw_value]
        if raw_value in SPECIAL_KEY_MAP:
            return SPECIAL_KEY_MAP[raw_value]
        if len(raw_value) == 1:
            return raw_value.upper()
        return raw_value

    assigned_key.short_description = 'Assigned Key'

    def edit_link(self, obj):
        return format_html('<a class="button" href="{}">Edit</a>', obj.pk and f'{obj.pk}/change/')

    edit_link.short_description = 'Action'