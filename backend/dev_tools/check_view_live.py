import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

# Force reload of views module to clear any cached state
import importlib
import api.views as views_module
importlib.reload(views_module)

from api.models import Norme, RuleTrainingSample

# Directly simulate what dataset_stats_api does for norm_id=4, dataset_type=classification
norm = Norme.objects.get(id=4)  # ISO 27001
standard = norm.name
dataset_type = 'classification'

is_evidence_mode = dataset_type in ('evidence', 'rule', 'rule_training', 'semantic')
is_classification_mode = dataset_type in ('classification', 'training')

print(f"dataset_type={dataset_type}")
print(f"is_evidence_mode={is_evidence_mode}")
print(f"is_classification_mode={is_classification_mode}")
print()

if is_classification_mode:
    qs = RuleTrainingSample.objects.filter(norm=norm)
    approved = qs.filter(label__iexact='approved').count()
    rejected = qs.filter(label__iexact='rejected').count()
    total = approved + rejected
    print(f"Classification mode → RuleTrainingSample:")
    print(f"  total_samples={total} approved={approved} rejected={rejected}")
    print(f"  CORRECT: {total > 0}")
