from django.core.management.base import BaseCommand
from django.db import connection
import redis
import time


class Command(BaseCommand):
    help = 'Clean up orphaned PaymentGatewayLog entries and optimize database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN MODE - No changes will be made")
        
        # Clean duplicate celery beat tasks
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM django_celery_beat_periodictask 
                WHERE name = 'update-exchange-rates-hourly'
            """)
            count = cursor.fetchone()[0]
            
            if count > 1:
                self.stdout.write(f"Found {count} duplicate celery beat tasks")
                if not dry_run:
                    cursor.execute("""
                        DELETE FROM django_celery_beat_periodictask 
                        WHERE name = 'update-exchange-rates-hourly' 
                        AND id NOT IN (
                            SELECT MIN(id) FROM django_celery_beat_periodictask 
                            WHERE name = 'update-exchange-rates-hourly'
                        )
                    """)
                    self.stdout.write("Cleaned duplicate celery beat tasks")
        
        # Check Redis health
        try:
            r = redis.StrictRedis(host='redis', port=6379, socket_timeout=2)
            info = r.info()
            memory_usage = info.get('used_memory_human', 'Unknown')
            self.stdout.write(f"Redis memory usage: {memory_usage}")
            
            # Check for large keys
            keys_count = r.dbsize()
            self.stdout.write(f"Redis keys count: {keys_count}")
            
        except Exception as e:
            self.stdout.write(f"Redis check failed: {e}")
        
        self.stdout.write("System cleanup completed")
