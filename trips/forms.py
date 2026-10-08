import re

from django import forms
from django.utils.translation import gettext, gettext_lazy as _

COUNTRY_CHOICES = [("japan", "Japan")]


class TripForm(forms.Form):
    destination = forms.ChoiceField(choices=COUNTRY_CHOICES, initial="japan", widget=forms.RadioSelect)
    ages = forms.CharField(
        label=_("How old is everyone going?"),
        help_text=_("One number per person, with commas. For example: 38, 36, 4, 2"),
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "38, 36, 4, 2"}),
    )
    start_date = forms.DateField(required=False, label=_("We leave on"), widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, label=_("We come home on"), widget=forms.DateInput(attrs={"type": "date"}))

    def clean_ages(self):
        parts = [p for p in re.split(r"[\s,;]+", self.cleaned_data["ages"]) if p]
        if not parts:
            raise forms.ValidationError(gettext("Add at least one age."))
        ages = []
        for p in parts:
            if not p.isdigit() or not 0 <= int(p) <= 120:
                raise forms.ValidationError(gettext('"%(value)s" is not an age. Use numbers like 38 or 4.') % {"value": p})
            ages.append(int(p))
        if len(ages) > 12:
            raise forms.ValidationError(gettext("That is a big family! The app takes up to 12 people."))
        return ages

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", gettext("The trip ends before it starts."))
        return data
