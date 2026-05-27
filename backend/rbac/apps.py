from django.apps import AppConfig


class RbacConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rbac'
    
    def ready(self):
        """Register signals when the app is ready"""
        import rbac.signals  # noqa

