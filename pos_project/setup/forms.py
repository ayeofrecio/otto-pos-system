from django import forms
from sales.models import POSFunction
from .widgets import KeyCaptureWidget


class PosFunctionForm(forms.ModelForm):
    class Meta:
        model = POSFunction
        fields = ['code', 'desc', 'key_code']  # ← key_code not keycode
        widgets = {
            'key_code': KeyCaptureWidget(),     # ← key_code not keycode
        }
        labels = {
            'code': 'Function Code',
            'desc': 'Description',
            'key_code': 'Assigned Key',         # ← key_code not keycode
        }
        help_texts = {
            'key_code': 'Click the field and press any key to assign it.',  # ← key_code not keycode
        }