from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from .models import track


@receiver(user_logged_in)
def on_login(request, user, **kwargs):
    track("signed_in", user=user)
