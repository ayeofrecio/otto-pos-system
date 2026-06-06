from django import forms
from sales.models import POSFunction


def _build_key_choices():
    function_keys = [
        (chr(0xDC), 'F1'),
        (chr(0xD8), 'F2'),
        (chr(0xE9), 'F3'),
        (chr(0xF7), 'F4'),
        (chr(0xF8), 'F5'),
        (chr(0xF9), 'F6'),
        (chr(0xFA), 'F7'),
        (chr(0xFB), 'F8'),
        (chr(0xFC), 'F9'),
        (chr(0xFD), 'F10'),
        (chr(0xFE), 'F11'),
        (chr(0xFF), 'F12'),
    ]

    navigation = [
        ('CR', 'Enter'), ('EC', 'Esc'), ('TB', 'Tab'), ('BK', 'Bksp'),
        ('HM', 'Home'), ('ND', 'End'), ('PU', 'PgUp'), ('PD', 'PgDn'),
        ('AU', 'Arrow Up'), ('AD', 'Arrow Down'), ('AL', 'Arrow Left'), ('AR', 'Arrow Right'),
        ('IC', 'Ins'), ('DL', 'Del'),
    ]

    digits = [(str(i), str(i)) for i in range(10)]
    letters = [(chr(code), chr(code)) for code in range(ord('A'), ord('Z') + 1)]

    return [
        ('Function Keys', function_keys),
        ('Navigation / Editing', navigation),
        ('Digits / Letters', digits + letters),
    ]


KEY_CHOICES = _build_key_choices()


class PosFunctionForm(forms.ModelForm):
    key_code = forms.ChoiceField(
        required=False,
        choices=KEY_CHOICES,
        label='Assigned Key',
        help_text='Pick a key from the grouped list.',
        widget=forms.Select(attrs={'style': 'min-width: 260px;'}),
    )

    class Meta:
        model = POSFunction
        fields = ['code', 'desc', 'key_code']
        labels = {
            'code': 'Function Code',
            'desc': 'Description',
            'key_code': 'Assigned Key',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = (self.instance.key_code or '').strip() if self.instance else ''
        if current and not any(
            current == value
            for _group, options in KEY_CHOICES
            for value, _label in options
        ):
            self.fields['key_code'].choices = [
                ('Current Value', [(current, current)]),
                *KEY_CHOICES,
            ]