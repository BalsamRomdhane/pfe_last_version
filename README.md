# Enterprise Management Platform

A production-ready enterprise platform with advanced RBAC, department-based organization, and secure authentication using Django and Keycloak.

## Architecture

- **Backend**: Django + Django REST Framework
- **Authentication**: Keycloak (OIDC)
- **Frontend**: React with Material-UI
- **Database**: PostgreSQL

## Setup

### Prerequisites

- Python 3.8+
- Node.js 14+
- Docker and Docker Compose

### 1. Start Infrastructure

```bash
cd docker
docker-compose up -d
```

This starts PostgreSQL and Keycloak.

### 2. Configure Keycloak

1. Access Keycloak at http://localhost:8081
2. Login with admin/admin
3. Create realm: `enterprise-realm`
4. Create client: `enterprise-client` (confidential, direct access grants enabled)
5. Create roles: ADMIN, TEAMLEAD, EMPLOYEE
6. Create users and assign roles/departments

### 3. Backend Setup

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Then edit backend/.env and fill your real Keycloak / Mailtrap values
python manage.py migrate
python manage.py runserver
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm start
```

## Features

- Role-based access control (ADMIN, TEAMLEAD, EMPLOYEE)
- Department-based organization (DIGITAL, AERONAUTIQUE, AUTOMOBILE, QUALITE)
- Dynamic UI theming
- User management for admins
- API testing panel
- Secure authentication via Keycloak

## API Endpoints

- POST /api/auth/login/ - Login
- POST /api/auth/users/ - Create user (ADMIN only)
- GET /api/protected/ - Protected endpoint
- GET /api/admin/ - Admin only
- GET /api/teamlead/ - Teamlead only
- GET /api/employee/ - Employee only

## Usage

1. Login with Keycloak credentials
2. Access dashboard based on role and department
3. Admins can create users


---

## Document Security Architecture (Phases 1–13)

La plateforme intègre une couche de sécurité documentaire de niveau Enterprise.
Voir [SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md) pour la documentation complète.

### Fonctionnalités de sécurité documentaire

| Fonctionnalité | Description |
|---|---|
| **Intégrité SHA-256** | Hash calculé à l'upload, vérifiable à tout moment |
| **Classification automatique** | PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED |
| **Chiffrement AES-256-GCM** | Chiffrement automatique des docs CONFIDENTIAL et RESTRICTED |
| **Stockage sécurisé** | Point d'accès unique, plaintext jamais sur disque |
| **Lecture sécurisée** | Endpoint RBAC + déchiffrement in-memory + streaming |
| **Téléchargement sécurisé** | RBAC + watermark automatique (PDF/DOCX) |
| **Journal d'audit** | Chaque action (VIEW/DOWNLOAD/INTEGRITY_CHECK) loggée |
| **Dashboard Admin** | KPIs chiffrement, distribution classification, historique audit |

### Configuration du chiffrement

```bash
# Générer une clé AES-256 sécurisée
python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Ajouter dans `backend/.env` :
```env
DOCUMENT_ENCRYPTION_KEY=<clé générée ci-dessus>
ENCRYPT_INTERNAL_DOCS=False   # True pour chiffrer aussi les docs INTERNAL
```

> **Important** : Sans `DOCUMENT_ENCRYPTION_KEY`, les documents CONFIDENTIAL et RESTRICTED
> sont analysés et classifiés mais **non chiffrés**. La clé est obligatoire en production.

### Endpoints sécurité

```
GET  /api/security/documents/<id>/integrity/   Vérifier l'intégrité SHA-256
GET  /api/security/documents/<id>/view/        Lire le document (streaming sécurisé)
GET  /api/security/documents/<id>/download/    Télécharger avec watermark
GET  /api/security/documents/<id>/audit/       Historique des actions
GET  /api/security/documents/<id>/analysis/    Rapport complet (PII, secrets, GDPR)
GET  /api/security/dashboard/admin/            Dashboard Admin enrichi
```

### Lancer les tests de sécurité

```bash
cd backend
python manage.py test \
  api.tests_phase1_hashing \
  api.tests_phase2_integrity_endpoint \
  api.tests_phase3_classification \
  api.tests_phase4_encryption \
  api.tests_phase5_storage \
  api.tests_phase6_secure_view \
  api.tests_phase7_download \
  api.tests_phase8_audit \
  --verbosity=1
# Résultat attendu : 263/263 tests ✅
```

### Nouvelles dépendances (Phase 7)

```
pypdf>=3.0.0       # Manipulation PDF pour watermark
reportlab>=4.0.0   # Génération du tampon watermark
```
