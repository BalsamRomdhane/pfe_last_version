# Document Security Workflow
## Enterprise ISO Compliance Platform

---

## Workflow complet — du dépôt à la consultation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EMPLOYEE — UPLOAD                                   │
│                                                                              │
│  1. Formulaire de soumission                                                 │
│     ├─ Sélection norme (ISO9001, ISO27001...)                                │
│     └─ Sélection fichier (PDF ou DOCX, max 20 MB)                           │
│                                                                              │
│  2. POST /api/documents/                                                     │
│     ├─ validate_uploaded_file() : extension, taille, MIME                   │
│     └─ Document.save() → file stocké sur disque (PLAINTEXT)                 │
│                                                                              │
│  3. Signal post_save → thread: doc-security-pipeline-{id}                   │
│     │                                                                        │
│     ├─── STEP 1 : SHA-256                                                    │
│     │    DocumentIntegrityService.compute_and_persist()                     │
│     │    → Document.sha256_hash (hash du plaintext)                         │
│     │                                                                        │
│     ├─── STEP 2 : Classification                                             │
│     │    ClassificationService.run()                                         │
│     │    → DocumentSecurityAnalysis.confidentiality_level                   │
│     │       PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED                   │
│     │                                                                        │
│     ├─── STEP 3 : Chiffrement (si CONFIDENTIAL ou RESTRICTED)               │
│     │    EncryptionService.encrypt_if_needed()                              │
│     │    → fichier remplacé par AES-256-GCM sur disque                      │
│     │    → Document.encrypted = True                                        │
│     │                                                                        │
│     └─── STEP 4 : Analyse sécurité (PII / secrets / GDPR)                  │
│          run_security_analysis()                                             │
│          → DocumentSecurityAnalysis (complet)                               │
│                                                                              │
│  4. Frontend Employee — Security Panel (polling)                             │
│     ├─ Classification + niveau de risque                                     │
│     ├─ Chiffrement + intégrité                                               │
│     ├─ PII count + secrets count                                             │
│     └─ Recommandations simplifiées                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TEAMLEAD — VALIDATION                                   │
│                                                                              │
│  1. Page Validations — sélection d'un document                               │
│     └─ Security Report (read-only) chargé automatiquement                   │
│        ├─ Classification + risk score (barre)                               │
│        ├─ PII détaillés par type                                             │
│        ├─ Secrets détectés                                                   │
│        ├─ GDPR compliance                                                    │
│        ├─ Recommandations complètes                                          │
│        └─ Audit de classification                                            │
│                                                                              │
│  2. Validation règle par règle (formulaire existant)                        │
│     └─ Décision finale : Approuvé / Rejeté                                  │
│                                                                              │
│  3. Lecture du document                                                      │
│     GET /api/security/documents/<id>/view/                                  │
│     ├─ RBAC (département)                                                    │
│     ├─ Déchiffrement in-memory si encrypted=True                            │
│     ├─ Streaming FileResponse                                                │
│     └─ Audit log → AuditLog(action=VIEW)                                    │
│                                                                              │
│  4. Téléchargement                                                           │
│     GET /api/security/documents/<id>/download/                              │
│     ├─ RBAC (département)                                                    │
│     ├─ Déchiffrement in-memory                                               │
│     ├─ Watermark (nom, date, heure, classification)                          │
│     └─ Audit log → AuditLog(action=DOWNLOAD)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADMIN — SUPERVISION                                  │
│                                                                              │
│  1. Dashboard Security (page Document Security)                              │
│     ├─ KPIs : analysés / chiffrés / PII total / secrets / haut risque       │
│     ├─ Barres : chiffrement (%) / intégrité (%)                             │
│     ├─ Distribution : classification / risque / GDPR                        │
│     ├─ Top PII types + top secrets                                           │
│     ├─ Documents haut risque (table)                                         │
│     └─ Historique audit (20 dernières actions)                              │
│                                                                              │
│  2. Vérification d'intégrité on-demand                                      │
│     GET /api/security/documents/<id>/integrity/                             │
│     → VERIFIED / TAMPERED / PENDING / FILE_MISSING                         │
│     → Audit log → AuditLog(action=INTEGRITY_CHECK)                          │
│                                                                              │
│  3. Analyse de sécurité on-demand                                           │
│     GET /api/security/documents/<id>/analysis/                              │
│     GET /api/security/documents/<id>/reanalyze/ (POST)                      │
│                                                                              │
│  4. Historique audit d'un document                                          │
│     GET /api/security/documents/<id>/audit/                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Diagramme de classification

```
SignauxInput:
  pii_count, pii_types, secret_count, risk_score, text_lower
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              ClassificationEngine.classify()             │
│                                                          │
│  Règles évaluées (par priorité décroissante) :          │
│                                                          │
│  P50  internal_keywords         → INTERNAL              │
│  P40  low_pii_or_risk           → INTERNAL              │
│  P30  medium_risk_score         → CONFIDENTIAL          │
│  P30  moderate_pii              → CONFIDENTIAL          │
│  P25  financial_or_hr_with_pii  → CONFIDENTIAL          │
│  P25  nda_or_legal              → CONFIDENTIAL          │
│  P15  high_risk_score           → RESTRICTED            │
│  P10  high_pii_or_financial_pii → RESTRICTED            │
│  P5   secret_detected           → RESTRICTED (toujours) │
│  P0   explicit_label            → dynamique (override)  │
│                                                          │
│  Niveau final = max(tous les niveaux déclenchés)        │
└─────────────────────────────────────────────────────────┘
         │
         ▼
  PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              EncryptionService.encrypt_if_needed()       │
│                                                          │
│  PUBLIC      → skip                                     │
│  INTERNAL    → skip (sauf ENCRYPT_INTERNAL_DOCS=True)   │
│  CONFIDENTIAL → AES-256-GCM ✓                           │
│  RESTRICTED   → AES-256-GCM ✓                           │
└─────────────────────────────────────────────────────────┘
```

---

## Format du fichier chiffré sur disque

```
┌──────────────┬────────────────────────────────────────┐
│ 12 bytes     │ N bytes                                │
│ Nonce GCM    │ Ciphertext + 16 bytes GCM auth tag     │
└──────────────┴────────────────────────────────────────┘

Taille totale = 12 (nonce) + len(plaintext) + 16 (tag)
               = len(plaintext) + 28 bytes overhead
```

---

## Politiques RBAC

| Action | ADMIN | TEAMLEAD | EMPLOYEE |
|---|---|---|---|
| Voir l'analyse sécurité | ✅ Tous | ✅ Son département | ✅ Ses docs |
| Vérifier l'intégrité | ✅ Tous | ✅ Son département | ✅ Ses docs |
| Lire le document (view) | ✅ Tous | ✅ Son département | ✅ Ses docs |
| Télécharger le document | ✅ Tous | ✅ Son département | ✅ Ses docs |
| Voir l'historique audit | ✅ Tous | ✅ Son département | ✅ Ses docs |
| Relancer l'analyse | ✅ Tous | ✅ Son département | ✅ Ses docs |
| Dashboard sécurité | ✅ Tous | ✅ (données dept) | ❌ |
| Dashboard Admin enrichi | ✅ Tous | ✅ (données dept) | ❌ |

---

## Garanties de sécurité et non-régression

### Ce qui ne change PAS
- L'endpoint `POST /api/documents/` est **identique** — pas de breaking change
- Les endpoints existants (`/api/documents/`, `/api/validations/`, `/api/compliance-os/`...) fonctionnent normalement
- Le pipeline ML (TrainingSample, RuleTrainingSample) continue de fonctionner
- Les notifications restent inchangées
- L'authentification Keycloak + JWT est conservée

### Nouvelles garanties
- Aucun fichier plaintext servi directement depuis `/media/` pour les documents chiffrés
- Le hash SHA-256 est calculé **avant** le chiffrement → la vérification d'intégrité fonctionne même sur fichiers chiffrés
- `extract_document_text()` déchiffre transparently → le pipeline ML fonctionne sur documents chiffrés
- `connection.close()` dans le thread pipeline → pas de fuite de connexions PostgreSQL sous Windows

---

## Migrations DB appliquées

| Migration | Modèle | Description |
|---|---|---|
| `api/0018` | `Document` | +sha256_hash, hash_algorithm, hash_created_at |
| `api/0019` | `Document` | +encrypted, encryption_iv, encrypted_at, encrypted_key_id |
| `api/0020` | `Document` | Ajustement max_length |
| `security/0001` | `DocumentSecurityAnalysis` | Modèle initial |
| `security/0002` | `DocumentSecurityAnalysis` | Renommage index |
| `security/0003` | `DocumentSecurityAnalysis` | +classification_source, classification_rules_matched |
| `compliance/0002` | `AuditLog` | +actions VIEW, DOWNLOAD, DECRYPT, INTEGRITY_CHECK, ENCRYPT, SECURITY_ANALYSIS |
