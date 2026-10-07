from django import forms


class EmailForm(forms.Form):
    email = forms.EmailField(
        label="Your email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com", "autofocus": True}),
    )
