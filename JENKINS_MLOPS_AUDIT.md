# Audit Jenkins/MLOps — Enterprise ISO Compliance Platform
> Généré après analyse complète du dépôt · Juin 2026

---

## A. AUDIT JENKINS/MLOPS

### A1. Architecture actuelle (réelle)

```
GitHub (lastversion/)
├── backend/
│   ├── enterprise_platform/     → Django settings, wsgi, urls
│   ├── api/
│   │   ├── models.py            → TrainingJob, TrainingSample, RuleTrainingSample,
│   │   │                          DocumentTrainingSample, MLOpsConfig, Norme, Rule, Document
│   │   ├── views.py             → 40+ endpoints REST (mlops_status, ml/train, drift, metrics)
│   │   ├── urls.py              → /api/ml/*, /api/metrics/, /api/compliance/drift/
│   │   └── management/commands/
│   │       ├── system_audit.py           ← audit DB (utilisé Stage 5)
│   │       ├── sync_all_datasets.py      ← sync RuleTS→TrainingTS (Stage 5)
│   │       ├── fill_ml_datasets.py       ← génère synthétique si < target (Stage 7)
│   │       ├── rebuild_training_datasets.py ← rebuild TS from real docs (Stage 5)
│   │       └── generate_training_datasets.py, generate_iso27001_tisax_datasets.py
│   ├── ml/
│   │   ├── train_models.py      → train_all_models() — RF, LR, GBT, BiLSTM
│   │   ├── train.py             → train_model() legacy (RF simple)
│   │   ├── dataset_builder.py   → buildTrainingDataset(), sync_training_samples_from_evidence()
│   │   ├── services.py          → compliance_service.retrain_models()
│   │   ├── semantic.py          → BiLSTMClassifier (sentence-transformers)
│   │   ├── search.py            → FAISS semantic search
│   │   ├── models/              → *.pkl (RF, LR, GBT, BiLSTM) + *_metrics.json
│   │   └── management/commands/
│   │       └── train_compliance.py ← COMMANDE PRINCIPALE (Stage 7)
│   └── services/
│       └── mlops_service.py     → compute_drift_score(), get_prometheus_metrics(),
│                                   trigger_jenkins_pipeline(), update_job_result()
└── frontend/
    ├── src/pages/EvidenceIntelligence.jsx
    └── package.json             → React 19, MUI, Tailwind, Keycloak-js
```

### A2. Modèles ML réellement entraînés (confirmés dans ml/models/)

| Standard | RandomForest | LogisticRegression | GradientBoosting | BiLSTM |
|----------|--------------|--------------------|------------------|--------|
| ISO 9001 | ✅ `.pkl` | ✅ `.pkl` | ✅ `.pkl` | ✅ `.pkl` |
| ISO 27001| ✅ `.pkl` | ✅ `.pkl` | ✅ `.pkl` | ✅ `.pkl` |
| TISAX    | ✅ `.pkl` | ✅ `.pkl` | ✅ `.pkl` | ✅ `.pkl` |

**Metriques ISO 9001 (dernière run — 2026-06-21) :**
- Best model: **BiLSTM** (f1=0.9943, acc=0.993)
- RandomForest: f1=0.972, acc=0.961
- GradientBoosting: f1=0.9524, acc=0.9351
- LogisticRegression: f1=0.9091, acc=0.8701

### A3. Flux MLOps réel

```
TeamLead valide Document
        ↓
Signal Django (Validation.post_save)
        ↓
create_training_sample() → TrainingSample + RuleTrainingSample
        ↓
sync_all_datasets (management cmd)
        ↓
fill_ml_datasets (complète si < target)
        ↓
train_compliance --standard X
        ↓  (appelle compliance_service.retrain_models)
        ↓  (appelle train_all_models dans ml/train_models.py)
        ↓
*.pkl sauvegardés dans ml/models/
*_metrics.json sauvegardés dans ml/models/
        ↓
TrainingJob créé / MLOpsConfig mis à jour
        ↓
get_prometheus_metrics() → /api/metrics/ (format text Prometheus)
        ↓
Prometheus scrape → Grafana dashboard
```

---

### A4. Points bloquants identifiés

| # | Problème | Fichier | Gravité |
|---|----------|---------|---------|
| 1 | `JENKINS_TOKEN` vide → trigger silencieux | `mlops_service.py` | HAUTE |
| 2 | `DB_NAME`/`DB_USER` absents → `ImproperlyConfigured` au démarrage | `settings.py` | HAUTE |
| 3 | BiLSTM nécessite PyTorch + Visual C++ Redistributable Windows | `requirements.txt` | HAUTE |
| 4 | `gensim` supprimé (commentaire dans requirements.txt) — `ml/vectorizers/__init__.py` importé avec try/except | `requirements.txt` | MOYENNE |
| 5 | `spacy en_core_web_sm` installé via URL directe GitHub — peut échouer sans accès réseau | `requirements.txt` | MOYENNE |
| 6 | ISO 27001 / TISAX : `TrainingSample` nécessite un `Document` FK — norms sans documents bloquent `rebuild_training_dataset` | `rebuild_training_dataset.py` | MOYENNE |
| 7 | Frontend `npm run build` suppose `node_modules` déjà présent | `package.json` | BASSE |
| 8 | `TrainingJob.log_output` n'existe pas dans `models.py` mais est utilisé dans `mlops_service.py` | `mlops_service.py:L100` | BASSE |

### A5. Dépendances Jenkins manquantes

- Plugin **Git** (checkout SCM)
- Plugin **Pipeline** (Jenkinsfile support)
- Plugin **JUnit** (publication résultats tests)
- Plugin **AnsiColor** (logs colorés)
- Plugin **Credentials Binding** (secrets)
- Plugin **GitHub Integration** (webhook)
- Plugin **Timestamper** (horodatage logs)
- Plugin **Workspace Cleanup** (cleanWs)

---

## B. JENKINSFILE — voir fichier `Jenkinsfile` à la racine

---

## C. CONFIGURATION JENKINS COMPLÈTE

### C1. Credentials à créer dans Jenkins
`Manage Jenkins → Credentials → Global → Add Credentials`

| ID Credential | Type | Valeur |
|---------------|------|--------|
| `DB_NAME` | Secret text | Nom de votre BDD PostgreSQL |
| `DB_USER` | Secret text | Utilisateur PostgreSQL |
| `DB_PASSWORD` | Secret text | Mot de passe PostgreSQL |
| `DB_HOST` | Secret text | `localhost` (local) |
| `DB_PORT` | Secret text | `5432` |
| `DJANGO_SECRET_KEY` | Secret text | Clé secrète Django (long random string) |
| `KEYCLOAK_SERVER_URL` | Secret text | `http://localhost:8081` |
| `KEYCLOAK_CLIENT_ID` | Secret text | `iso9001-client` |
| `KEYCLOAK_CLIENT_SECRET` | Secret text | Votre secret Keycloak |

### C2. Variables d'environnement requises (hors credentials)

Ajouter dans `Manage Jenkins → System → Global properties → Environment variables` :

```
DJANGO_SETTINGS_MODULE = enterprise_platform.settings
ALLOWED_HOSTS          = localhost,127.0.0.1
DEBUG                  = False
JENKINS_URL            = http://localhost:8080
JENKINS_JOB_NAME       = compliance-ml-pipeline
```

### C3. Configuration Pipeline — Script from SCM

1. `New Item` → `Pipeline`
2. Nom : `compliance-ml-pipeline`
3. Section **Pipeline** :
   - **Definition** : `Pipeline script from SCM`
   - **SCM** : `Git`
   - **Repository URL** : `https://github.com/<votre-compte>/lastversion.git`
   - **Credentials** : GitHub token (type `Username with password`)
   - **Branch** : `*/main`
   - **Script Path** : `Jenkinsfile`
4. Section **Build Triggers** :
   - Cocher `GitHub hook trigger for GITScm polling`

### C4. Configuration GitHub Webhook

1. Aller dans `Settings → Webhooks → Add webhook` sur votre dépôt GitHub
2. **Payload URL** : `http://<IP-Jenkins>:8080/github-webhook/`
3. **Content type** : `application/json`
4. **Events** : `Just the push event`
5. **Active** : ✅

> Si Jenkins est local et non exposé sur internet, utiliser **ngrok** :
> ```
> ngrok http 8080
> ```
> Puis utiliser l'URL ngrok comme Payload URL.

---

## D. COMPATIBILITÉ WINDOWS — Vérifications

| Point | Statut | Note |
|-------|--------|------|
| `bat` exclusivement (pas `sh`) | ✅ | Tous les stages utilisent `bat` |
| Séparateur de chemin `\\` | ✅ | Chemins Windows dans toutes les variables |
| `.venv\\Scripts\\python.exe` | ✅ | Chemin Windows venv |
| `mkdir` avec `IF NOT EXIST` | ✅ | Évite erreur si dossier existe |
| `copy /Y` pour les modèles | ✅ | Commande Windows native |
| `FOR %%F IN (...)` | ✅ | Boucle batch Windows |
| `findstr` au lieu de `grep` | ✅ | Filtre Windows |
| Pas de `&&` → `&` batch | ✅ | Séparateur Windows |
| `SET VAR=` pour env vars | ✅ | Syntaxe CMD Windows |

---

## E. ARCHITECTURE MLOPS FINALE

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GITHUB (push → webhook)                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    JENKINS (local Windows)                          │
│  Pipeline: compliance-ml-pipeline                                   │
│                                                                     │
│  Stage 1: Checkout ──────────────────────────────────────────────►  │
│  Stage 2: pip install requirements.txt ─────────────────────────►  │
│  Stage 3: manage.py check + migrate ────────────────────────────►  │
│  Stage 4: pytest api/tests.py ──────────────────────────────────►  │
│  Stage 5: system_audit + sync_all_datasets ─────────────────────►  │
│  Stage 6: compute_drift_score() ────────────────────────────────►  │
│  Stage 7: train_compliance --standard X ────────────────────────►  │
│  Stage 8: lecture *_metrics.json ───────────────────────────────►  │
│  Stage 9: get_prometheus_metrics() ─────────────────────────────►  │
│  Stage 10: TrainingJob.objects.create() ────────────────────────►  │
│  Stage 11: npm run build ───────────────────────────────────────►  │
│  Stage 12: archiveArtifacts ────────────────────────────────────►  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┴───────────────────┐
              ▼                                    ▼
┌─────────────────────────┐          ┌─────────────────────────────┐
│   DJANGO BACKEND        │          │   ML MODELS (ml/models/)    │
│   (PostgreSQL)          │          │                             │
│                         │          │  ISO9001_RandomForest.pkl   │
│   TrainingJob ──────────┼──────►   │  ISO9001_GradientBoosting   │
│   MLOpsConfig ──────────┼──────►   │  ISO9001_LogisticRegression │
│   TrainingSample        │          │  ISO9001_BiLSTM.pkl         │
│   RuleTrainingSample    │          │  *_metrics.json             │
│                         │          │  evidence_index.faiss       │
│   /api/metrics/ ────────┼──────►   └─────────────────────────────┘
└─────────────┬───────────┘
              │ Prometheus scrape
              ▼
┌─────────────────────────┐
│   PROMETHEUS            │
│   (localhost:9090)      │
│                         │
│  compliance_model_f1    │
│  compliance_drift_score │
│  compliance_docs_total  │
└─────────────┬───────────┘
              │
              ▼
┌─────────────────────────┐
│   GRAFANA               │
│   (localhost:3001)      │
│   Dashboard MLOps       │
└─────────────────────────┘
```

---

## F. ÉTAPES EXACTES POUR EXÉCUTER LE PIPELINE

### Étape 1 — Prérequis Windows
```powershell
# Python 3.11 installé et accessible depuis PATH
python --version   # doit afficher 3.11.x

# Node.js installé
node --version     # doit afficher 18.x ou 20.x

# PostgreSQL en cours d'exécution
# Jenkins en cours d'exécution sur http://localhost:8080
```

### Étape 2 — Créer les credentials Jenkins
Suivre la section C1 ci-dessus.

### Étape 3 — Créer le job Jenkins
Suivre la section C3 ci-dessus.

### Étape 4 — Premier run manuel
1. Aller dans le job `compliance-ml-pipeline`
2. Cliquer `Build with Parameters`
3. Choisir `STANDARD = ALL`, `FORCE_RETRAIN = false`
4. Cliquer `Build`

### Étape 5 — Vérifier les artefacts
Après le build, dans le menu du build :
- `Test Result` → résultats pytest
- `Archived Artifacts` → drift_report.json, evaluation_summary.json,
  prometheus_metrics.txt, models/*.pkl, models/*_metrics.json

### Étape 6 — Activer le webhook GitHub (déclenchement automatique)
Suivre la section C4.

---

## G. CORRECTIONS NÉCESSAIRES AVANT MISE EN PRODUCTION

### Priorité HAUTE

1. **`TrainingJob.log_output` manquant** — `mlops_service.py` écrit sur ce champ
   mais `models.py` ne le déclare pas.
   ```python
   # Ajouter dans TrainingJob (models.py) :
   log_output = models.TextField(blank=True, default='')
   # Puis : python manage.py makemigrations && python manage.py migrate
   ```

2. **`JENKINS_TOKEN` obligatoire** — Sans ce token, `trigger_jenkins_pipeline()`
   retourne silencieusement `{'triggered': False}` sans erreur. Configurer la
   credential Jenkins et l'env var `JENKINS_TOKEN`.

3. **PyTorch/BiLSTM sur Windows** — BiLSTM nécessite Visual C++ Redistributable
   2015-2022 (x64). Si non installé, `ml/semantic.py` échoue et le flag
   `_BILSTM_AVAILABLE = False` désactive silencieusement BiLSTM.
   Solution : installer [VC_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### Priorité MOYENNE

4. **`DJANGO_SECRET_KEY` exposée dans settings.py** — La clé par défaut
   `django-insecure-+q0*_7...` est hardcodée. En production, forcer via env var
   et supprimer la valeur par défaut.

5. **`KEYCLOAK_CLIENT_SECRET` hardcodée** — `d3XqSEHRtQHKXIEHC0GztCzgXojUOF9O`
   visible dans `settings.py`. À déplacer impérativement en variable d'environnement.

6. **spaCy model URL directe** — `requirements.txt` installe `en_core_web_sm`
   via URL GitHub. En environnement sans accès internet :
   ```
   python -m spacy download en_core_web_sm
   ```

7. **ISO 27001 / TISAX — Documents manquants** — `rebuild_training_dataset.py`
   (Path B) ne peut pas créer de `TrainingSample` sans `Document` FK.
   Utiliser `fill_ml_datasets` qui crée des Documents synthétiques.

### Priorité BASSE

8. **Pytest vs Django test runner** — `api/tests.py` est un `TestCase` Django
   (pas pytest pur). Utiliser `manage.py test api` pour garantir la compatibilité
   ou ajouter `pytest-django` dans `requirements.txt`.

9. **`generate_training_datasets.py` — double définition de `Command`** — Le
   fichier contient deux classes `Command`. Seule la dernière est chargée.
   Supprimer la première occurrence.

10. **`mlops_service.py` — import `Document.Status` depuis string** — Les
    comparaisons `status_source in [Document.Status.APPROVED, ...]` fonctionnent
    mais mélangent valeurs textuelles et enum. Uniformiser avec `.value`.

---

## H. DIAGRAMME WORKFLOW COMPLET

```
GitHub Push
    │
    ▼ (webhook)
Jenkins Stage 1: git checkout
    │
    ▼
Jenkins Stage 2: pip install requirements.txt
    │  (.venv\Scripts\pip.exe install)
    ▼
Jenkins Stage 3: manage.py check + migrate
    │  (valide models + DB PostgreSQL)
    ▼
Jenkins Stage 4: pytest api/tests.py
    │  (DashboardStatsTests, DatasetStatsViewTests, TrainingDatasetBuilderTests)
    ▼
Jenkins Stage 5: manage.py system_audit + sync_all_datasets
    │  (compte Norme/Rule/Document/TrainingSample/RuleTrainingSample)
    │  (sync RuleTrainingSample → TrainingSample via sync_training_samples_from_evidence())
    ▼
Jenkins Stage 6: compute_drift_score(standard)
    │  (TF-IDF cosine similarity: historical 70% vs recent 30%)
    │  (→ drift_report.json)
    ▼
Jenkins Stage 7: manage.py train_compliance --standard X
    │  (→ compliance_service.retrain_models())
    │  (→ train_all_models() dans ml/train_models.py)
    │  (→ RandomForest + LogisticRegression + GradientBoosting + BiLSTM)
    │  (→ sauvegarde ml/models/*.pkl + *_metrics.json)
    ▼
Jenkins Stage 8: lecture *_metrics.json
    │  (accuracy, f1, precision, recall par modèle et par norme)
    │  (→ evaluation_summary.json)
    ▼
Jenkins Stage 9: get_prometheus_metrics()
    │  (compliance_documents_total, compliance_model_f1_score,
    │   compliance_drift_score, compliance_training_jobs_total)
    │  (→ prometheus_metrics.txt)
    ▼
Jenkins Stage 10: TrainingJob.objects.create() + MLOpsConfig.update_or_create()
    │  (enregistre le run dans PostgreSQL)
    │  (met à jour last_trained_at, current_model_version, last_f1_score)
    ▼
Jenkins Stage 11: npm run build (React frontend)
    │
    ▼
Jenkins Stage 12: archiveArtifacts (*.pkl, *.json, metrics.txt)
    │
    ▼ (post-build)
Django /api/metrics/ ──► Prometheus ──► Grafana
    │                         │
    │                         └── compliance_model_f1_score{standard="ISO9001"}
    │                         └── compliance_drift_score{standard="ISO27001"}
    │                         └── compliance_documents_total
    │
    └── TrainingJob.status = 'success'
    └── MLOpsConfig.current_model_version = 'jenkins-build-X-BiLSTM'
```
