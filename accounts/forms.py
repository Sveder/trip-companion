from allauth.account.forms import ConfirmLoginCodeForm
from django import forms
from django.utils.translation import gettext, gettext_lazy as _


class EmailForm(forms.Form):
    email = forms.EmailField(
        label=_("Your email"),
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com", "autofocus": True}),
    )


class SixDigitCodeForm(ConfirmLoginCodeForm):
    """The sign-in code box: 6 digits, so a phone opens the number pad."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].label = gettext("Your 6-digit code")
        self.fields["code"].widget.attrs.update(
            {"inputmode": "numeric", "pattern": "[0-9]*", "maxlength": "6",
             "placeholder": "123456", "autofocus": True, "autocomplete": "one-time-code"}
        )
