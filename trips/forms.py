from django import forms
from django.utils.translation import gettext, gettext_lazy as _

from .models import GROUP_AGES, GROUP_IDS


def country_choices():
    """Every place in content/previews.yaml that is ready (feedback T171 made Uzbekistan the second one)."""
    from content_admin.loader import load_previews
    return [(c["id"], c["name"]) for c in load_previews() if c.get("ready") and not c.get("href")]


class TripForm(forms.Form):
    destination = forms.ChoiceField(choices=country_choices, initial="japan", widget=forms.RadioSelect)
    # Feedback T53: how many people in each age group. The plane picker fills these; without JavaScript they are number boxes.
    little = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    kid = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    big = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    grownup = forms.IntegerField(min_value=0, max_value=12, required=False, initial=0)
    # Feedback T54: the leave date is optional; the family gives the trip length instead of a return date.
    length_days = forms.IntegerField(min_value=1, max_value=90, required=False, label=_("How many days is the trip?"),
                                     widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": "10"}))
    start_date = forms.DateField(required=False, label=_("We leave on (if you know)"), widget=forms.DateInput(attrs={"type": "date"}))

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
        return data
