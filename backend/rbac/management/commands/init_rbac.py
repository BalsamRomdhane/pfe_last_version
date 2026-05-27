from django.core.management.base import BaseCommand
from rbac.models import Department, Role

class Command(BaseCommand):
    help = 'Initialize default departments and roles'

    def handle(self, *args, **kwargs):
        # Create departments
        departments_data = [
            {'code': 'DIGITAL', 'name': 'Digital Operations', 'theme_color': '#1976d2'},
            {'code': 'AERONAUTIQUE', 'name': 'Aeronautics', 'theme_color': '#9c27b0'},
            {'code': 'AUTOMOBILE', 'name': 'Automobile Production', 'theme_color': '#4caf50'},
            {'code': 'QUALITE', 'name': 'Quality Management', 'theme_color': '#ff9800'},
        ]
        
        for dept_data in departments_data:
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults={'name': dept_data['name'], 'theme_color': dept_data['theme_color']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created department: {dept.code}"))
            else:
                self.stdout.write(f"Department {dept.code} already exists")
        
        # Create roles
        roles_data = [
            {'code': 'ADMIN', 'name': 'Administrator'},
            {'code': 'TEAMLEAD', 'name': 'Team Lead'},
            {'code': 'EMPLOYEE', 'name': 'Employee'},
        ]
        
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={'name': role_data['name']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {role.code}"))
            else:
                self.stdout.write(f"Role {role.code} already exists")
