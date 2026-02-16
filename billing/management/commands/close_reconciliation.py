from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from billing.models import ReconciliationRun


class Command(BaseCommand):
    help = "Close a GePG reconciliation business date to enforce cut-off control."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="trx_date",
            help="Business date to close (YYYY-MM-DD). Defaults to yesterday.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Close even if run is not in PROCESSED status.",
        )

    def handle(self, *args, **options):
        trx_date_raw = options.get("trx_date")
        force = bool(options.get("force"))

        if trx_date_raw:
            try:
                trx_date = date.fromisoformat(trx_date_raw)
            except ValueError as exc:
                raise CommandError("Invalid --date; expected YYYY-MM-DD") from exc
        else:
            trx_date = timezone.localdate() - timezone.timedelta(days=1)

        runs = ReconciliationRun.objects.filter(trx_date=trx_date).order_by("-created_at")
        if not runs.exists():
            raise CommandError(f"No reconciliation runs found for {trx_date}")

        # Close the latest run for the date (others remain as audit history).
        run = runs.first()

        if run.status == "CLOSED":
            self.stdout.write(self.style.SUCCESS(f"Already closed: {trx_date} ({run.req_id})"))
            return

        if run.status != "PROCESSED" and not force:
            raise CommandError(
                f"Run {run.req_id} status is {run.status}; re-run reconciliation or use --force to close."
            )

        now = timezone.now()
        run.status = "CLOSED"
        run.closed_at = now
        run.save(update_fields=["status", "closed_at", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"Closed reconciliation: {trx_date} ({run.req_id})"))

