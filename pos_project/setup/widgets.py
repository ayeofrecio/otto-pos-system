from django import forms


class KeyCaptureWidget(forms.TextInput):
    """
    Lets the user pick a key with the mouse and stores the underlying keycode value.
    """
    class Media:
        css = {
            'all': ('setup/css/key-capture.css',)
        }
        js = ('setup/js/key_capture.js?v=18',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'key-capture-input',
            'placeholder': 'No key selected',
            'autocomplete': 'off',
            'readonly': 'readonly',
            'tabindex': '-1',
        })