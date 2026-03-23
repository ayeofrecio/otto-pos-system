from django import forms


class KeyCaptureWidget(forms.TextInput):
    """
    Captures the actual key the user presses and stores it in the keycode field.
    """
    class Media:
        css = {
            'all': ('setup/css/key_capture.css',)
        }
        js = ('setup/js/key_capture.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'key-capture-input',
            'readonly': 'readonly',
            'placeholder': 'Click here, then press a key...',
            'autocomplete': 'off',
        })