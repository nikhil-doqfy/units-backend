from django.apps import AppConfig


class LeaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lease'

    def ready(self):
        import lease.signals  # noqa: F401
