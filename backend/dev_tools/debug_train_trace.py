import os
import traceback
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from ml.train_models import train_all_models

try:
    result = train_all_models(standard=None, norme_id=1, dataset_type='classification')
    print('RESULT:', result)
except Exception:
    traceback.print_exc()
