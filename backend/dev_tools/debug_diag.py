import os
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django

django.setup()

from rest_framework.test import APIRequestFactory
from api.views import ml_diagnostics_api
from django.contrib.auth.models import AnonymousUser

rf = APIRequestFactory()
req = rf.get('/api/ml/diagnostics/', {'norm_id': 4})
req.user = AnonymousUser()

try:
    resp = ml_diagnostics_api(req)
    print('STATUS=', resp.status_code)
    print('DATA=', resp.data)
except Exception:
    print('EXCEPTION OCCURRED')
    traceback.print_exc()
    sys.exit(1)
