from django import forms
from django.utils.translation import gettext, gettext_lazy as _

from .models import GROUP_AGES, GROUP_IDS

COUNTRY_CHOICES = [("japan", "Japan")]


class TripForm(forms.Form):
    destination = forms.ChoiceField(choices=COUNTRY_CHOICES, initial="japan", widget=forms.RadioSelect)
    # Feedback T53: how many people in each age group. The plane picker fills these; without JavaScript they are number boxes.
    little = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    kid = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    big = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    grownup = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    start_date = forms.DateField(required=False, label=_("We leave on"), widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, label=_("We come home on"), widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        counts = {g: data.get(g) or 0 for g in GROUP_IDS}
        total = sum(counts.values())
        if total == 0:
            raise forms.ValidationError(gettext("Put at least one person on the plane."))
        if total > 12:
            raise forms.ValidationError(gettext("That is a big family! The app takes up to 12 people."))
        data["counts"] = counts
        data["ages"] = [GROUP_AGES[g] for g in GROUP_IDS for n in range(counts[g])]
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", gettext("The trip ends before it starts."))
        return data
