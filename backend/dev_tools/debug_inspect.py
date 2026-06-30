import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django

django.setup()

from rest_framework.test import APIRequestFactory
from api.models import Norme, RuleTrainingSample, TrainingSample
from api.views import dataset_stats_api, evidence_status_api, ml_diagnostics_api

factory = APIRequestFactory()

norms = list(Norme.objects.all()[:5])
print('NORMS:', [(n.id, n.name) for n in norms])
print('RULETRAINING rows:', RuleTrainingSample.objects.count())
print('TRAININGSAMPLE rows:', TrainingSample.objects.count())

for norm in norms[:3]:
    req = factory.get(f'/dataset-stats/?norm_id={norm.id}&dataset_type=classification')
    resp = dataset_stats_api(req)
    print(f'\nCLASSIFICATION NORM {norm.id} {norm.name}')
    print('STATUS', resp.status_code)
    print('DATA KEYS', sorted(resp.data.keys()))
    print('TOTAL', resp.data.get('total_samples'))
    print('APPROVED', resp.data.get('approved_samples'))
    print('REJECTED', resp.data.get('rejected_samples'))
    print('TOTAL_ALL', resp.data.get('total_all'))
    print('SAMPLES_LEN', len(resp.data.get('samples', [])))
    print('FIRST_SAMPLE', resp.data.get('samples', [])[:1])

    req2 = factory.get(f'/dataset-stats/?norm_id={norm.id}&dataset_type=evidence')
    resp2 = dataset_stats_api(req2)
    print(f'\nEVIDENCE NORM {norm.id} {norm.name}')
    print('STATUS', resp2.status_code)
    print('TOTAL', resp2.data.get('total_samples'))
    print('APPROVED', resp2.data.get('approved_samples'))
    print('REJECTED', resp2.data.get('rejected_samples'))
    print('SAMPLES_LEN', len(resp2.data.get('samples', [])))
    print('FIRST_SAMPLE', resp2.data.get('samples', [])[:1])

    req3 = factory.get(f'/ml/diagnostics/?norm_id={norm.id}')
    resp3 = ml_diagnostics_api(req3)
    print(f'\nDIAG NORM {norm.id} {norm.name}')
    print(resp3.data)

req4 = factory.get('/evidence/status/')
resp4 = evidence_status_api(req4)
print('\nEVIDENCE STATUS GLOBAL')
print(resp4.data)
