from django.core.management.base import BaseCommand
from api.models import Norme


class Command(BaseCommand):
    help = 'Delete a Norme by exact name from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='Exact name of the Norme to delete'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Delete without prompting for confirmation'
        )

    def handle(self, *args, **options):
        name = options['name'].strip()
        force = options['force']

        if not force:
            confirm = input(f"Delete Norme with name '{name}'? This will remove the norm and all its rules. [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Aborted. No changes made.'))
                return

        normes = Norme.objects.filter(name__iexact=name)
        count = normes.count()
        if count == 0:
            self.stdout.write(self.style.ERROR(f"No Norme found with name '{name}'"))
            return

        for norme in normes:
            norme.delete()

        self.stdout.write(self.style.SUCCESS(f"Deleted {count} Norme(s) with name '{name}'"))
