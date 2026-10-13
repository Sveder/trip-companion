from django import forms
from django.utils.translation import gettext, gettext_lazy as _

from .models import GROUP_AGES, GROUP_IDS


def country_choices():
    """Every place in content/previews.yaml that is ready (feedback T171 made Uzbekistan the second one)."""
    from content_admin.loader import load_previews
    return [(c["id"], c["name"]) for c in load_previews() if c.get("ready") and not c.get("href")]


def module_ids():
    from content_admin.models import Module
    return list(Module.objects.values_list("id", flat=True))


class TripForm(forms.Form):
    destination = forms.ChoiceField(choices=country_choices, initial="japan", widget=forms.RadioSelect)
    # Feedback T264: how many kids and grown-ups. The - and + buttons change these number boxes.
    kid = forms.IntegerField(min_value=0, max_value=12, required=False, initial=1)
    grownup = forms.IntegerField(min_value=0, max_value=12, required=False, initial=2)
    # Feedback T264: the module switches sit on the same page. The view checks them against the chosen country.
    modules = forms.TypedMultipleChoiceField(coerce=int, required=False, choices=lambda: [(i, i) for i in module_ids()])
    # Feedback T54: the leave date is optional; the family gives the trip length instead of a return date.
    length_days = forms.IntegerField(min_value=1, max_value=90, required=False, label=_("How many days is the trip?"),
                                     widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": "10"}))
    start_date = forms.DateField(required=False, label=_("We leave on (if you know)"), widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        counts = {g: data.get(g) or 0 for g in GROUP_IDS}
        total = sum(counts.values())
        if total == 0:
            raise forms.ValidationError(gettext("Add at least one person."))
        if total > 12:
            raise forms.ValidationError(gettext("That is a big family! The app takes up to 12 people."))
        data["counts"] = counts
        data["ages"] = [GROUP_AGES[g] for g in GROUP_IDS for n in range(counts[g])]
        from content_admin.models import Module
        from courses.builder import fits_counts
        here = Module.objects.filter(country=data.get("destination"))
        if "modules_shown" in self.data:
            chosen = {m.id for m in here if m.id in set(data.get("modules") or [])}
        else:
            # A form with no module list (an old page in the browser cache) gets the modules that fit the family.
            chosen = {m.id for m in here if fits_counts(m, counts)}
        if data.get("destination") and not chosen:
            self.add_error("modules", gettext("Pick at least one thing to learn."))
        data["modules"] = sorted(chosen)
        return data
