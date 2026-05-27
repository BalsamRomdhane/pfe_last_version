from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from rbac.models import UserProfile, Role
import sys


class Command(BaseCommand):
    help = 'Create a global admin account'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for the admin account (default: admin)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@example.com',
            help='Email for the admin account (default: admin@example.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Password for the admin account (will prompt if not provided)'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            # Update superuser status if not already set
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Existing user {username} upgraded to superuser'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✓ User {username} is already a superuser'))
            
            # Ensure UserProfile exists with ADMIN role
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': Role.objects.get_or_create(
                        code='ADMIN',
                        defaults={
                            'name': 'Administrator',
                            'description': 'Global system administrator'
                        }
                    )[0],
                    'department': None
                }
            )
            
            # Print summary
            self._print_admin_summary(user, profile)
            return

        # Prompt for password if not provided
        if not password:
            password = self._prompt_password()

        try:
            # Create Django superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Django superuser created: {username}'))

            # Get or create ADMIN role
            admin_role, created = Role.objects.get_or_create(
                code='ADMIN',
                defaults={
                    'name': 'Administrator',
                    'description': 'Global system administrator'
                }
            )

            # Create UserProfile with ADMIN role (no department)
            profile = UserProfile.objects.create(
                user=user,
                role=admin_role,
                department=None  # Admin has no department
            )
            self.stdout.write(self.style.SUCCESS(f'✓ RBAC UserProfile created with ADMIN role'))

            # Print summary
            self._print_admin_summary(user, profile)

        except Exception as e:
            # Clean up user if profile creation fails
            if User.objects.filter(username=username).exists():
                User.objects.get(username=username).delete()
            raise CommandError(f'Failed to create admin account: {str(e)}')

    def _print_admin_summary(self, user, profile):
        """Print admin account summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Global Admin Account Configured!'))
        self.stdout.write('='*60)
        self.stdout.write(f'Username: {user.username}')
        self.stdout.write(f'Email: {user.email}')
        self.stdout.write(f'Role: {profile.role.code} (Global Administrator)')
        self.stdout.write(f'Department: None (Global Access)')
        self.stdout.write(f'Superuser: {user.is_superuser}')
        self.stdout.write(f'Staff: {user.is_staff}')
        self.stdout.write('='*60 + '\n')

    def _prompt_password(self):
        """Prompt user for password with confirmation"""
        import getpass
        
        while True:
            password = getpass.getpass('Enter password for admin account: ')
            if len(password) < 8:
                self.stdout.write(self.style.WARNING('Password must be at least 8 characters!'))
                continue
            
            password_confirm = getpass.getpass('Confirm password: ')
            if password != password_confirm:
                self.stdout.write(self.style.WARNING('Passwords do not match!'))
                continue
            
            return password
