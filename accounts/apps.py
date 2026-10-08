from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from allauth.account.signals import user_signed_up

        from analytics.models import track

        def google_signed_up(request, user, sociallogin=None, **kwargs):
            # The email-code path tracks its own signups in views.user_for_email.
            if sociallogin is not None:
                track("signed_up", user=user, method=sociallogin.account.provider)

        user_signed_up.connect(google_signed_up, dispatch_uid="accounts-google-signed-up", weak=False)
