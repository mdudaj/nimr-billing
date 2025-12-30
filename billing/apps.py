import json
import sys

from django.apps import AppConfig
from django.conf import settings
from django.db.utils import IntegrityError, OperationalError


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        # Avoid DB work during management commands that operate on model state.
        # Hitting a remote/unavailable DB here can hang makemigrations/migrate.
        if any(
            cmd in sys.argv for cmd in ["makemigrations", "migrate", "showmigrations"]
        ):
            return

        from django.db import connection
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        try:
            # Check if tables exist before trying to access them
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'django_celery_beat_intervalschedule'
                    );
                """
                )
                tables_exist = cursor.fetchone()[0]

            if tables_exist:
                self.setup_periodic_tasks(IntervalSchedule, PeriodicTask)
        except (OperationalError, IntegrityError, Exception):
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
