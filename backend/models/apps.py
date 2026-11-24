from django.apps import AppConfig
from django.db.models.signals import post_delete


class ModelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "models"
    verbose_name = "3D-модели"

    def ready(self):
        def delete_file(sender, instance, **kwargs):
            if instance.file:
                instance.file.delete(save=False)

        post_delete.connect(delete_file, sender="models.PrintModel")
