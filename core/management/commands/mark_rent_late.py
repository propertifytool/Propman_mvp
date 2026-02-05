from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import RentPayment


class Command(BaseCommand):
    help = "Mark rent payments as LATE when due_date has passed and status is still DUE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be updated without saving changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        today = date.today()

        qs = RentPayment.objects.filter(
            status=RentPayment.Status.DUE,
            due_date__lt=today,
        )

        count = qs.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would mark {count} payment(s) as LATE."))
            return

        updated = qs.update(status=RentPayment.Status.LATE)
        self.stdout.write(self.style.SUCCESS(f"Marked {updated} payment(s) as LATE."))
