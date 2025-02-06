import json

from django.apps import AppConfig
from django.conf import settings


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        self.setup_periodic_tasks(IntervalSchedule, PeriodicTask)

    def setup_periodic_tasks(self, IntervalSchedule, PeriodicTask):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=1, period=IntervalSchedule.HOURS
        )

        task_name = "update-exchange-rates-hourly"
        task_url = settings.EXCRATES_URL

        # Delete existing task if it exists
        PeriodicTask.objects.filter(name=task_name).delete()

        PeriodicTask.objects.update_or_create(
            interval=schedule,
            name=task_name,
            defaults={
                "task": "billing.tasks.update_exchange_rates",
                "interval": schedule,
                "args": json.dumps([task_url]),
                "enabled": True,
            },
        )
