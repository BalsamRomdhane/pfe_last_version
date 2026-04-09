from rest_framework.permissions import BasePermission

class KeycloakRolePermission(BasePermission):
    required_role = None

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        return self.required_role in getattr(user, 'roles', [])

class IsAdmin(KeycloakRolePermission):
    required_role = 'ADMIN'

class IsTeamLead(KeycloakRolePermission):
    required_role = 'TEAMLEAD'

class IsEmployee(KeycloakRolePermission):
    required_role = 'EMPLOYEE'

class DepartmentAccess(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False

        roles = getattr(user, 'roles', [])
        department = getattr(user, 'department', None)

        if 'ADMIN' in roles:
            return True
        if 'TEAMLEAD' in roles or 'EMPLOYEE' in roles:
            return bool(department)
        return False