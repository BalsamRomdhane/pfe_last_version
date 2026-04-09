from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rbac.models import UserProfile, Department, Role


class Command(BaseCommand):
    help = 'Create test users with Django profiles (assumes users already exist in Keycloak)'

    def handle(self, *args, **options):
        # Get or create user objects (must match Keycloak usernames exactly)
        test_users = [
            {
                'username': 'admin1',
                'email': 'admin1@example.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'role_code': 'ADMIN',
                'department_code': None,  # ADMIN has no department
            },
            {
                'username': 'teamlead1',
                'email': 'teamlead1@example.com',
                'first_name': 'Team',
                'last_name': 'Lead',
                'role_code': 'TEAMLEAD',
                'department_code': 'DIGITAL',
            },
            {
                'username': 'employee1',
                'email': 'employee1@example.com',
                'first_name': 'Employee',
                'last_name': 'One',
                'role_code': 'EMPLOYEE',
                'department_code': 'DIGITAL',
            },
            {
                'username': 'employee2',
                'email': 'employee2@example.com',
                'first_name': 'Employee',
                'last_name': 'Two',
                'role_code': 'EMPLOYEE',
                'department_code': 'AERONAUTIQUE',
            },
        ]

        for user_data in test_users:
            username = user_data['username']
            role_code = user_data['role_code']
            department_code = user_data['department_code']

            # Get or create Django user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Django user: {username}'))
            else:
                self.stdout.write(f'User already exists: {username}')

            # Get role and department
            role = Role.objects.get(code=role_code)
            department = Department.objects.get(code=department_code) if department_code else None

            # Get or create UserProfile
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': role,
                    'department': department,
                }
            )

            if profile_created:
                self.stdout.write(self.style.SUCCESS(f'Created UserProfile: {username} ({role_code})'))
            else:
                self.stdout.write(f'UserProfile already exists: {username}')

        self.stdout.write(self.style.SUCCESS('All test users created successfully'))
