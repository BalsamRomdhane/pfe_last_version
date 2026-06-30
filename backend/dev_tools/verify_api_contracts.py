import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django
django.setup()
from rest_framework.test import APIClient
from django.contrib.auth.models import User

client = APIClient()
user = User.objects.first()
if user is None:
    print('NO USER FOUND')
    raise SystemExit(1)
client.force_authenticate(user=user)

urls = [
    '/api/evidence/status/',
    '/api/rule-memory/?page=1&page_size=5&sort=newest',
    '/api/evidence/duplicates/',
    '/api/dataset/quality-report/',
]

for url in urls:
    resp = client.get(url)
    print(f'URL: {url}')
    print(f'STATUS: {resp.status_code}')
    try:
        body = resp.json()
    except Exception:
        body = resp.content.decode('utf-8', errors='ignore')
    print(json.dumps(body, indent=2, ensure_ascii=False, default=str)[:12000])
    print('\n---\n')
