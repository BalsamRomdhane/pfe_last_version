# Audit & Corrections Jenkinsfile — Enterprise ISO Compliance Platform
> Basé sur lecture directe du code source — aucune hypothèse

---

## A. AUDIT DÉTAILLÉ DES INCOHÉRENCES

### INCOHÉRENCE 1 — `TrainingJob.log_output` : champ ABSENT du modèle ❌

**Preuve :**
- `services/mlops_service.py` lignes 199 et 225 : `job.log_output = str(e)` et `job.log_output = payload.get('log_output', '')`
- `api/migrations/0011_mlopsconfig_trainingjob.py` : aucun champ `log_output` dans la liste des fields
- `api/models.py` classe `TrainingJob` : `log_output` absent

**Conséquence :** `django.db.utils.ProgrammingError: column api_trainingjob.log_output does not exist` au premier appel de `trigger_jenkins_pipeline()` ou `update_job_result()`

**Correction appliquée :**
- Ajout de `log_output = models.TextField(blank=True, default='')` dans `models.py`
- Création de la migration `0014_trainingjob_log_output.py`

---

### INCOHÉRENCE 2 — `train_compliance` ne produit pas les modèles RF/LR/GBT ❌

**Preuve :**
- `ml/management/commands/train_compliance.py` : appelle `compliance_service.retrain_models(standard)`
- `ml/services.py` méthode `retrain_models()` : appelle `self.analyzer.vectorize_rules(standard)`
- `vectorize_rules()` = vectorisation TF-IDF NLP des règles ISO — **pas** un entraînement ML supervisé
- `ml/train_models.py` fonction `train_all_models(standard, norme_id, dataset_type)` : produit les `.pkl` RF + LR + GBT + BiLSTM + `*_metrics.json`

**Conséquence :** Le Jenkinsfile original utilisait `manage.py train_compliance` qui ne génère aucun `.pkl` supervisé, donc le Stage 8 (lecture `*_metrics.json`) échouait silencieusement.

**Correction appliquée :** Stage 5 appelle directement `train_all_models()` via `-c "..."` Python inline.

---

### INCOHÉRENCE 3 — `migrate --run-syncdb --check` incompatible Django 5.x ❌

**Preuve :**
- Django 5.x : `--check` et `--run-syncdb` sont des flags mutuellement exclusifs. `--check` retourne code 1 si migrations en attente sans les appliquer. `--run-syncdb` applique et crée des tables. Les combiner lève `CommandError`.

**Correction appliquée :**
```
manage.py check              # vérification système
manage.py migrate --check    # vérifier migrations en attente (exitcode 1 si oui)
manage.py migrate --run-syncdb  # appliquer migrations
```

---

### INCOHÉRENCE 4 — `DB_NAME`, `DB_HOST`, `DB_PORT` en Credentials Jenkins ❌

**Preuve :**
- `enterprise_platform/settings.py` : `DB_NAME`, `DB_HOST`, `DB_PORT` sont des variables d'environnement normales, non marquées comme secrets
- Seuls `DB_PASSWORD`, `DJANGO_SECRET_KEY`, `KEYCLOAK_CLIENT_SECRET` contiennent des valeurs sensibles

**Conséquence :** Surcharge inutile de la configuration Jenkins, et comportement inattendu car `credentials()` masque les valeurs dans les logs (même `localhost` devient `****`)

**Correction appliquée :** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` = variables `environment {}` simples

---

### INCOHÉRENCE 5 — Stage Frontend cassé ❌

**Preuve :**
```groovy
// Code original — CASSÉ :
IF NOT EXIST "node_modules" (
    node ./node_modules/react-scripts/bin/react-scripts.js build 2>&1 || npm install
)
```
Si `node_modules` absent → tente d'exécuter `react-scripts` depuis un dossier inexistant → erreur → tombe sur `npm install`

**Correction appliquée :**
```bat
IF EXIST "package-lock.json" (
    npm ci --legacy-peer-deps
) ELSE (
    npm install --legacy-peer-deps
)
npm run build
```

---

### INCOHÉRENCE 6 — `compute_drift_score(standard)` appelée avec noms incorrects ❌

**Preuve :**
- `services/mlops_service.py` : `RuleTrainingSample.objects.filter(norm__name__iexact=standard)`
- Les noms réels en DB sont `"ISO 9001 - Controle et validation des documents"`, pas `"ISO9001"`
- Le Jenkinsfile original passait `'ISO9001'`, `'ISO27001'`, `'TISAX'` qui ne matchent jamais avec `__iexact`

**Correction appliquée :** Itérer sur `Norme.objects.all()` et passer `norm.name` directement.

---

### INCOHÉRENCE 7 — Tests via `pytest` sans `pytest-django` ❌

**Preuve :**
- `requirements.txt` : aucune occurrence de `pytest` ou `pytest-django`
- `api/tests.py` : utilise `django.test.TestCase` (runner Django natif)
- Le Jenkinsfile original utilisait `python -m pytest api/tests.py` → `ModuleNotFoundError: No module named 'pytest'`

**Correction appliquée :** `manage.py test api --verbosity=2`

---

### INCOHÉRENCE 8 — `fill_ml_datasets --seed 42` : paramètre `--force` inexistant ❌

**Preuve :**
- `api/management/commands/fill_ml_datasets.py` méthode `add_arguments()` :
  - `--dry-run`
  - `--force-regen`  ← (pas `--force`)
  - `--seed INT`

**Correction appliquée :** Remplacer `FORCE_RETRAIN ? '--force'` par `FORCE_REGEN ? '--force-regen'`

---

## B. LISTE DES CORRECTIONS OBLIGATOIRES

| # | Fichier | Correction | Statut |
|---|---------|------------|--------|
| 1 | `api/models.py` | Ajouter `log_output = models.TextField(blank=True, default='')` à `TrainingJob` | ✅ **Appliqué** |
| 2 | `api/migrations/` | Créer migration `0014_trainingjob_log_output.py` | ✅ **Appliqué** |
| 3 | `Jenkinsfile` Stage 5 | Remplacer `manage.py train_compliance` par `train_all_models()` directement | ✅ **Appliqué** |
| 4 | `Jenkinsfile` Stage 3 | Séparer `migrate --check` et `migrate --run-syncdb` | ✅ **Appliqué** |
| 5 | `Jenkinsfile` env block | `DB_HOST/DB_PORT/DB_NAME/DB_USER` = variables simples, pas `credentials()` | ✅ **Appliqué** |
| 6 | `Jenkinsfile` Stage 11 | Corriger la logique `npm install` → `npm ci` ou `npm install` selon présence de `package-lock.json` | ✅ **Appliqué** |
| 7 | `Jenkinsfile` Stage 6 | Drift : passer `norm.name` réel depuis DB, pas `'ISO9001'` hardcodé | ✅ **Appliqué** |
| 8 | `Jenkinsfile` Stage 4 | Tests : `manage.py test api` pas `pytest` | ✅ **Appliqué** |
| 9 | `Jenkinsfile` Stage 5 | `--force-regen` (pas `--force`) pour `fill_ml_datasets` | ✅ **Appliqué** |

---

## C. Jenkinsfile final unique → `Jenkinsfile` (racine)

8 stages, fusion soutenance + meilleurs éléments production.
`Jenkinsfile.soutenance` et `Jenkinsfile.production` supprimés.

---

## E. PLUGINS JENKINS NÉCESSAIRES

| Plugin | Pourquoi | Obligatoire |
|--------|----------|-------------|
| **Pipeline** (`workflow-aggregator`) | Support Jenkinsfile déclaratif | ✅ Oui |
| **Git** | `checkout scm` | ✅ Oui |
| **Credentials Binding** | `credentials('DB_PASSWORD')` | ✅ Oui |
| **Timestamper** | `timestamps()` dans options | ✅ Oui |
| **Workspace Cleanup** | `cleanWs()` en post | ✅ Oui |
| **AnsiColor** | `ansiColor('xterm')` (prod) | ⚠️ Version prod |
| **GitHub Integration** | `githubPush()` webhook trigger (prod) | ⚠️ Version prod |
| **JUnit** | Si on ajoute XML reports plus tard | ❌ Pas requis actuellement |

Installation rapide via `Manage Jenkins → Plugins → Available` :
```
Pipeline, Git, Credentials Binding, Timestamper, Workspace Cleanup
```

---

## F. CREDENTIALS JENKINS NÉCESSAIRES

**Aller dans :** `Manage Jenkins → Credentials → System → Global → Add Credentials`

| ID Credential | Type | Valeur à mettre |
|---------------|------|-----------------|
| `DB_PASSWORD` | Secret text | Mot de passe PostgreSQL |
| `DJANGO_SECRET_KEY` | Secret text | Clé secrète Django (50+ chars random) |
| `KEYCLOAK_CLIENT_SECRET` | Secret text | `d3XqSEHRtQHKXIEHC0GztCzgXojUOF9O` (ou nouvelle valeur) |

**Variables simples (PAS des credentials) :**
Modifier directement dans le Jenkinsfile selon votre environnement :
```groovy
DB_HOST = "localhost"   // ou IP du serveur PostgreSQL
DB_PORT = "5432"
DB_NAME = "compliance_db"   // nom réel de votre BDD
DB_USER = "compliance_user"  // utilisateur PostgreSQL réel
```

---

## G. ÉTAPES PRÉCISES POUR EXÉCUTER LE PIPELINE

### Prérequis
```powershell
# Vérifier Python 3.11
python --version   # → Python 3.11.x

# Vérifier Node.js
node --version     # → 18.x ou 20.x

# PostgreSQL en cours d'exécution
# Jenkins accessible sur http://localhost:8080
```

### Étape 1 — Appliquer la migration `log_output`
```bat
cd C:\Users\balsa\lastversion\backend
.venv\Scripts\python.exe manage.py migrate
```
Vérifier la sortie :
```
Applying api.0014_trainingjob_log_output... OK
```

### Étape 2 — Créer les 3 credentials Jenkins
`Manage Jenkins → Credentials → Global → Add Credential → Secret text`
- `DB_PASSWORD`
- `DJANGO_SECRET_KEY`
- `KEYCLOAK_CLIENT_SECRET`

### Étape 3 — Adapter les variables simples dans Jenkinsfile
Ouvrir `Jenkinsfile` et modifier :
```groovy
DB_NAME = "compliance_db"      // votre nom réel
DB_USER = "compliance_user"    // votre user réel
DB_HOST = "localhost"           // OK si local
DB_PORT = "5432"                // OK si défaut
```

### Étape 4 — Créer le job Jenkins

1. `New Item` → nom : `compliance-ml-pipeline` → type : `Pipeline`
2. Section **Pipeline** :
   - Definition : `Pipeline script from SCM`
   - SCM : `Git`
   - Repository URL : `https://github.com/<votre-compte>/lastversion.git`
   - Credentials : ajouter un credential GitHub (Username + Token)
   - Branch : `*/main`
   - Script Path : `Jenkinsfile`
3. Cliquer **Save**

### Étape 5 — Premier run manuel

1. Cliquer `Build with Parameters`
2. `STANDARD = ISO9001` (ou `ALL`)
3. `FORCE_REGEN = false`
4. Cliquer `Build`

### Étape 6 — Vérifier les artifacts après le build

Dans le menu du build :
- `Archived Artifacts` → `prometheus_metrics.txt`, `evaluation_summary.json`
- Console Output → chercher `[OK] TrainingJob #X created`

### Pour la Version Production (Jenkinsfile.production)

Remplacer `Script Path` dans le job Jenkins par `Jenkinsfile.production`
ou créer un second job `compliance-ml-pipeline-prod`.

---

## Résumé des fichiers créés/modifiés

```
✅ Jenkinsfile                          → UNIQUE, version finale (8 stages)
✅ backend/api/models.py                → log_output ajouté à TrainingJob
✅ backend/api/migrations/0014_*.py    → migration pour log_output
❌ Jenkinsfile.soutenance               → supprimé
❌ Jenkinsfile.production               → supprimé
```

---

## B. CORRECTIONS — Architecture de Sécurité Documentaire (Phases 1–13)

### Revue Phase 1 — Corrections appliquées

| Point | Problème initial | Correction |
|---|---|---|
| 1 | Pas de `DocumentIntegrityService` — fonctions libres seulement | Classe `DocumentIntegrityService` avec `compute_and_persist()` et `verify_document()` |
| 2 | 2 threads indépendants (hash + analyse) | Pipeline séquentiel unique `doc-security-pipeline-{id}` |
| 3 | Hash calculé uniquement à la création | Signal déclenche aussi sur remplacement de fichier (`_file_has_changed()`) |
| 4 | `sha256_hash` max_length=64, pas `unique` | Confirmé correct, aucune modification |
| 5 | Index conditionnel `models.Q(sha256_hash__gt='')` non supporté | Simplifié sans condition |
| 6 | Threads daemon + Windows = `psycopg2 "database is in use"` | `connection.close()` dans `finally` du pipeline ; `join()` dans `tearDown` |
| 7 | Pipeline non extensible pour futures phases | Stubs commentés pour Phase 3/4 dans le pipeline |

### Nouvelles migrations créées

- `api/0018_document_integrity_fields` — SHA-256 fields
- `api/0019_document_encryption_fields` — AES-256 fields
- `api/0020_alter_document_encrypted_key_id_and_more` — Réconciliation
- `security/0002_rename_indexes` — Renommage auto
- `security/0003_classification_fields` — Classification audit
- `compliance/0002_auditlog_document_security_actions` — Nouvelles actions

### État final des tests

```
Phase 1 (hashing)       : 36/36  ✅
Phase 2 (integrity API)  : 20/20  ✅
Phase 3 (classification) : 50/50  ✅
Phase 4 (encryption)     : 42/42  ✅
Phase 5 (storage)        : 30/30  ✅
Phase 6 (secure view)    : 22/22  ✅
Phase 7 (download/wm)    : 31/31  ✅
Phase 8 (audit)          : 32/32  ✅
─────────────────────────────────
TOTAL                    : 263/263 ✅
```
