from rest_framework.permissions import BasePermission

class KeycloakRolePermission(BasePermission):
    required_role = None

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False

        roles = getattr(user, 'roles', []) or []
        if not isinstance(roles, list):
            roles = [roles]
        normalized_roles = [str(role).upper() for role in roles if role]
        return self.required_role.upper() in normalized_roles

class IsAdmin(KeycloakRolePermission):
    required_role = 'ADMIN'

class IsTeamLead(KeycloakRolePermission):
    required_role = 'TEAMLEAD'

class IsTeamLeadOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False

        roles = getattr(user, 'roles', []) or []
        if not isinstance(roles, list):
            roles = [roles]
        normalized_roles = [str(role).upper() for role in roles if role]
        return 'ADMIN' in normalized_roles or 'TEAMLEAD' in normalized_roles

class IsEmployee(KeycloakRolePermission):
    required_role = 'EMPLOYEE'

class DepartmentAccess(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False

        roles = getattr(user, 'roles', []) or []
        if not isinstance(roles, list):
            roles = [roles]
        normalized_roles = [str(role).upper() for role in roles if role]
        department = getattr(user, 'department', None)

        if 'ADMIN' in normalized_roles:
            return True
        if 'TEAMLEAD' in normalized_roles or 'EMPLOYEE' in normalized_roles:
            return bool(department)
        return False