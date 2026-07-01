# Document Security Architecture
## Enterprise ISO Compliance Platform

---

## Vue d'ensemble

Ce document décrit l'architecture de sécurité documentaire mise en place dans la plateforme Enterprise ISO Compliance. Elle couvre l'intégralité du cycle de vie sécurisé d'un document, depuis l'upload jusqu'à la suppression, en passant par la classification, le chiffrement, la vérification d'intégrité, le téléchargement sécurisé et l'audit.

---

## Architecture du pipeline de sécurité

À chaque upload d'un document, un pipeline séquentiel s'exécute en arrière-plan (daemon thread unique par document) :

```
POST /api/documents/
    └─► Document.save() → signal post_save
         └─► thread: doc-security-pipeline-{id}
              │
              ├─► Phase 1 : DocumentIntegrityService.compute_and_persist()
              │       SHA-256 calculé sur le plaintext
              │       → Document.sha256_hash, hash_algorithm, hash_created_at
              │
              ├─► Phase 3 : ClassificationService.run()
              │       Moteur de classification (9 règles)
              │       → DocumentSecurityAnalysis.confidentiality_level
              │       → classification_source, classification_rules_matched
              │
              ├─► Phase 4 : EncryptionService.encrypt_if_needed()
              │       AES-256-GCM si CONFIDENTIAL ou RESTRICTED
              │       → Document.encrypted, encrypted_at, encrypted_key_id
              │
              └─► run_security_analysis() [existant]
                      PII, secrets, GDPR, risque
                      → DocumentSecurityAnalysis (complet)
              finally: connection.close()
```

---

## Phases implémentées

### Phase 1 — Intégrité SHA-256
- **Service** : `backend/services/security/hashing.py`
- **Classe** : `DocumentIntegrityService`
- **Fonctions** : `calculate_sha256()`, `verify_sha256()`, `hash_document_file()`
- **Endpoint** : `GET /api/security/documents/<id>/integrity/`
- **Champs DB** : `Document.sha256_hash`, `hash_algorithm`, `hash_created_at`
- **Politique** : Hash calculé sur le plaintext AVANT chiffrement. Recalculé si le fichier est remplacé.

### Phase 2 — Vérification d'intégrité
- **Endpoint** : `GET /api/security/documents/<id>/integrity/`
- **Réponse** : `{ is_valid, status (VERIFIED|PENDING|TAMPERED|FILE_MISSING), stored_hash, computed_hash, reason }`
- **RBAC** : Admin=tous, TeamLead=département, Employee=ses documents

### Phase 3 — Classification automatique
- **Service** : `backend/services/security/classification.py`
- **Classe** : `ClassificationEngine`, `ClassificationService`
- **Niveaux** : `PUBLIC` → `INTERNAL` → `CONFIDENTIAL` → `RESTRICTED`
- **Règles** (9, par priorité croissante) :
  - `internal_keywords` : draft, WIP, not for distribution
  - `low_pii_or_risk` : 1 PII ou risk 20–49
  - `medium_risk_score` : risk 50–74
  - `moderate_pii` : 2–4 PII
  - `financial_or_hr_with_pii` : données financières/RH + PII
  - `nda_or_legal` : NDA, contrat
  - `high_risk_score` : risk ≥ 75
  - `high_pii_or_financial_pii` : ≥5 PII ou IBAN/CC/NID
  - `secret_detected` : tout secret → toujours RESTRICTED
  - `explicit_classification_label` : label dans le texte (override)

### Phase 4 — Chiffrement AES-256-GCM
- **Service** : `backend/services/security/encryption.py`
- **Algorithme** : AES-256-GCM (nonce 12 bytes, tag 16 bytes)
- **Format** : `[12 bytes nonce] + [ciphertext + 16 bytes tag]`
- **Clé** : `DOCUMENT_ENCRYPTION_KEY` (env var, base64url, 32 bytes) — **jamais en dur**
- **Politique** :

| Classification | Chiffrement |
|---|---|
| PUBLIC | Jamais |
| INTERNAL | Si `ENCRYPT_INTERNAL_DOCS=True` (défaut: False) |
| CONFIDENTIAL | Toujours |
| RESTRICTED | Toujours |

- **Décryptage** : toujours en mémoire (`decrypt_in_memory()`), jamais sur disque
- **Champs DB** : `Document.encrypted`, `encryption_iv`, `encrypted_at`, `encrypted_key_id`

### Phase 5 — DocumentStorageService
- **Service** : `backend/services/document_storage.py`
- **Classe** : `DocumentStorageService`
- **Méthodes** :
  - `read_raw(doc_id)` → bytes bruts (ciphertext si chiffré)
  - `read_plaintext(doc_id)` → plaintext (déchiffre transparently)
  - `open_plaintext_stream(doc_id)` → `io.BytesIO` pour streaming HTTP
  - `write(doc_id, data)` → écrit les bytes sur le chemin existant
  - `delete(doc_id)` → supprime le fichier
  - `exists(doc_id)`, `get_filename(doc_id)`
- **Principe** : point d'accès unique. Le plaintext ne touche jamais le disque.

### Phase 6 — Lecture sécurisée (Secure View)
- **Endpoint** : `GET /api/security/documents/<id>/view/`
- **Réponse** : `FileResponse` (streaming in-memory)
- **Headers** :
  - `Content-Disposition: inline`
  - `Cache-Control: no-store, no-cache, must-revalidate, private`
  - `X-Content-Type-Options: nosniff`
- **RBAC** : Admin=tous, TeamLead=département, Employee=ses documents
- **Frontend** : `useSecureDocumentView.openDocument()` — fetch via JWT + Blob URL

### Phase 7 — Téléchargement sécurisé (Secure Download + Watermark)
- **Endpoint** : `GET /api/security/documents/<id>/download/?watermark=true`
- **Réponse** : `HttpResponse` avec `Content-Disposition: attachment`
- **Watermark** :
  - PDF : tampon diagonal semi-transparent (reportlab + pypdf)
  - DOCX : paragraphe header (gris, italique)
  - Contenu : `Downloaded by / Date / Time / Classification`
  - Désactivable : `?watermark=false`
- **Frontend** : `useSecureDocumentView.downloadDocument()` — `<a download>` simulé

### Phase 8 — Journal d'audit documentaire
- **Service** : `backend/services/security/document_audit.py`
- **Classe** : `DocumentAuditService`
- **Stockage** : `compliance.AuditLog` (réutilisation de l'infrastructure existante)
- **Actions loggées** : `VIEW`, `DOWNLOAD`, `INTEGRITY_CHECK`, `ENCRYPT`, `SECURITY_ANALYSIS`
- **Champs** : `entity_type=Document`, `entity_id`, `action`, `performed_by`, `ip_address`, `new_value` (contexte JSON)
- **Endpoint** : `GET /api/security/documents/<id>/audit/`

---

## Modèles Django modifiés

### `api.Document` — champs ajoutés

| Champ | Type | Description |
|---|---|---|
| `sha256_hash` | CharField(64) | Hash SHA-256 du fichier au moment de l'upload |
| `hash_algorithm` | CharField(16) | Algorithme (toujours `sha256`) |
| `hash_created_at` | DateTimeField | Date de calcul du hash |
| `encrypted` | BooleanField | True si le fichier est chiffré AES-256-GCM |
| `encryption_iv` | CharField(24) | Nonce base64 (informatif) |
| `encrypted_at` | DateTimeField | Date du chiffrement |
| `encrypted_key_id` | CharField(64) | Identifiant de la clé (`env_key`) |

### `security.DocumentSecurityAnalysis` — champs ajoutés

| Champ | Type | Description |
|---|---|---|
| `classification_source` | CharField(64) | Règle déterminante |
| `classification_rules_matched` | JSONField | Liste de toutes les règles qui ont déclenché |

### `compliance.AuditLog` — actions ajoutées
`VIEW`, `DOWNLOAD`, `DECRYPT`, `INTEGRITY_CHECK`, `ENCRYPT`, `SECURITY_ANALYSIS`

---

## API Endpoints de sécurité

| Endpoint | Méthode | Description | RBAC |
|---|---|---|---|
| `/api/security/documents/<id>/analysis/` | GET | Rapport d'analyse complet | A/TL/E(own) |
| `/api/security/documents/<id>/integrity/` | GET | Vérification SHA-256 | A/TL/E(own) |
| `/api/security/documents/<id>/view/` | GET | Lecture sécurisée (streaming) | A/TL(dept)/E(own) |
| `/api/security/documents/<id>/download/` | GET | Téléchargement + watermark | A/TL(dept)/E(own) |
| `/api/security/documents/<id>/audit/` | GET | Historique des actions | A/TL(dept)/E(own) |
| `/api/security/documents/<id>/reanalyze/` | POST | Relancer l'analyse | A/TL/E(own) |
| `/api/security/documents/list/` | GET | Liste documents (dropdown) | Auth |
| `/api/security/scan/` | POST | Scan fichier (sans sauvegarde) | Auth |
| `/api/security/dashboard/` | GET | KPIs résumés | TL/A |
| `/api/security/dashboard/statistics/` | GET | Statistiques détaillées | TL/A |
| `/api/security/dashboard/high-risk/` | GET | Documents haut risque | TL/A |
| `/api/security/dashboard/admin/` | GET | Dashboard Admin enrichi | TL/A |

---

## Variables d'environnement

| Variable | Description | Obligatoire |
|---|---|---|
| `DOCUMENT_ENCRYPTION_KEY` | Clé AES-256 base64url (32 bytes) | En production |
| `ENCRYPT_INTERNAL_DOCS` | Chiffrer aussi les docs INTERNAL (défaut: False) | Non |

**Générer une clé :**
```bash
python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

---

## Structure des fichiers

```
backend/
├── services/
│   ├── document_storage.py          # Phase 5 — StorageService
│   └── security/
│       ├── hashing.py               # Phase 1 — SHA-256
│       ├── encryption.py            # Phase 4 — AES-256-GCM
│       ├── classification.py        # Phase 3 — Moteur de classification
│       ├── document_audit.py        # Phase 8 — Journal d'audit
│       ├── watermark.py             # Phase 7 — Watermark PDF/DOCX
│       ├── pii_detector.py          # Détection PII (existant)
│       ├── secret_detector.py       # Détection secrets (existant)
│       ├── risk_scoring.py          # Scoring risque (existant)
│       ├── gdpr_checker.py          # Conformité GDPR (existant)
│       ├── metadata_analyzer.py     # Métadonnées (existant)
│       └── recommendation_engine.py # Recommandations (existant)
│
├── security/
│   ├── models.py                    # DocumentSecurityAnalysis
│   ├── views.py                     # Tous les endpoints sécurité
│   ├── urls.py                      # Routes sécurité
│   ├── serializers.py               # Serializers sécurité
│   └── signals.py                   # Pipeline (post_save Document)
│
├── compliance/
│   ├── models.py                    # AuditLog (enrichi Phase 8)
│   └── services.py                  # create_audit_log()
│
└── api/
    ├── models.py                    # Document (champs intégrité + chiffrement)
    ├── serializers.py               # DocumentSerializer (nouveaux champs)
    └── utils.py                     # extract_document_text() — encryption-aware

frontend/
├── src/
│   ├── hooks/
│   │   ├── useSecureDocumentView.js # Phase 6/7 — view + download
│   │   └── useDocumentSecurity.js   # Phase 9/10 — fetch analyse sécurité
│   └── components/
│       ├── SecurityBadge.jsx        # Badges classification/intégrité/chiffrement
│       ├── DocumentSecurityPanel.jsx # Panneau Employee (Phase 9)
│       └── TeamLeadSecurityReport.jsx # Rapport complet TeamLead (Phase 10)
```

---

## Tests

| Suite | Tests | Description |
|---|---|---|
| `tests_phase1_hashing.py` | 36 | SHA-256 service, modèle, signal, pipeline |
| `tests_phase2_integrity_endpoint.py` | 20 | Endpoint integrity, RBAC, serializer |
| `tests_phase3_classification.py` | 50 | Moteur classification, règles, service, pipeline |
| `tests_phase4_encryption.py` | 42 | AES-256-GCM, policy, DB, decrypt, extract_text |
| `tests_phase5_storage.py` | 30 | StorageService, callers, intégration |
| `tests_phase6_secure_view.py` | 22 | Endpoint view, RBAC, headers, contenu |
| `tests_phase7_download.py` | 31 | Watermark, endpoint download, RBAC, headers |
| `tests_phase8_audit.py` | 32 | AuditService, actions, endpoint historique |
| **Total** | **263** | **Tous passing ✅** |

---

## Garanties de sécurité

1. **Plaintext jamais sur disque** — Le déchiffrement est toujours in-memory via `BytesIO`
2. **Clé jamais codée** — `DOCUMENT_ENCRYPTION_KEY` uniquement via variables d'environnement
3. **RBAC sur chaque endpoint** — Admin/TeamLead(dept)/Employee(own)
4. **Hash avant chiffrement** — SHA-256 calculé sur le plaintext (Phase 1 avant Phase 4)
5. **GCM authentifié** — Toute altération du ciphertext lève `InvalidTag` avant libération du plaintext
6. **Pas de cache navigateur** — `Cache-Control: no-store` sur tous les endpoints de fichier
7. **Audit complet** — Chaque action VIEW/DOWNLOAD/INTEGRITY_CHECK loggée avec IP et contexte
8. **JWT obligatoire** — Aucun fichier servi via `/media/` direct ; tout passe par les endpoints sécurisés
