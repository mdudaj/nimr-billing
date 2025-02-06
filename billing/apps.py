import json

from django.apps import AppConfig
from django.conf import settings
from django.db.utils import IntegrityError, OperationalError


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        try:
            # Create interval schedule and periodic task
            self.setup_periodic_tasks(IntervalSchedule, PeriodicTask)
        except (OperationalError, IntegrityError):
            # Avoid errors during migrations or when the database is not ready
            pass

    def setup_periodic_tasks(self, IntervalSchedule, PeriodicTask):
        # Ensure that there is only one interval schedule
        schedule = IntervalSchedule.objects.filter(
            every=1, period=IntervalSchedule.HOURS
        ).first()
        if not schedule:
            schedule = IntervalSchedule.objects.create(
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
