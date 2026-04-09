from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from authentication.permissions import IsAdmin, IsTeamLead, IsEmployee, DepartmentAccess

class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "This is a protected endpoint", "user": request.user.username if request.user else None})

class AdminView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({"message": "Admin access granted"})

class TeamLeadView(APIView):
    permission_classes = [IsTeamLead]

    def get(self, request):
        return Response({"message": "TeamLead access granted"})

class EmployeeView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request):
        return Response({"message": "Employee access granted"})
