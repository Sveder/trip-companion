from django.apps import AppConfig


class ContentAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'content_admin'

    def ready(self):
        from .sites import setup

        setup()
