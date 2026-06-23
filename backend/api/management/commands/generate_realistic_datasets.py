"""
generate_realistic_datasets — Génère des datasets ML réalistes pour ISO 27001 et TISAX.

Chaque document contient 150-500 mots de texte professionnel réaliste.
Les TrainingSample et RuleTrainingSample sont enrichis avec du texte réel.

Usage:
    python manage.py generate_realistic_datasets
    python manage.py generate_realistic_datasets --norm ISO27001 --count 500
    python manage.py generate_realistic_datasets --norm TISAX --count 500
"""
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import (
    Norme, Rule, Document, Validation,
    TrainingSample, RuleTrainingSample,
    aggregate_validation_metrics, extract_features, build_validation_feature_vector,
)

# ── ISO 27001 — Documents réalistes ─────────────────────────────────────────

ISO27001_COMPLIANT_DOCS = [
    {
        'title': 'Politique de contrôle des accès',
        'theme': 'gestion_acces',
        'text': """
Politique de Contrôle des Accès — Référence : PSI-ACC-2026-001 — Version 3.2 — Approuvée le 15/03/2026

1. OBJET ET DOMAINE D'APPLICATION
Cette politique définit les exigences de contrôle des accès aux systèmes d'information de l'organisation, conformément à la norme ISO/IEC 27001:2022, clause A.5.15. Elle s'applique à l'ensemble des systèmes, applications, bases de données et infrastructures réseau gérés par la Direction des Systèmes d'Information.

2. PRINCIPES DIRECTEURS
Le contrôle des accès repose sur le principe du moindre privilège : chaque utilisateur dispose uniquement des droits nécessaires à l'exercice de ses fonctions. L'accès aux ressources sensibles est soumis à une authentification multi-facteurs (MFA) obligatoire. Les comptes à privilèges (administrateurs, super-utilisateurs) font l'objet d'une gestion renforcée via un outil PAM (Privileged Access Management).

3. GESTION DU CYCLE DE VIE DES COMPTES
3.1 Création : tout nouveau compte est créé sur demande formelle du responsable hiérarchique et validé par la DSI. Le formulaire de demande d'accès (FDA-001) doit être complété, signé et archivé.
3.2 Modification : toute modification de droits fait l'objet d'une demande identique et est tracée dans le SIEM.
3.3 Révocation : lors d'un départ ou changement de poste, le compte est désactivé dans les 24h suivant la notification RH. Les droits résiduels sont audités trimestriellement.

4. REVUE DES DROITS D'ACCÈS
Une revue formelle des droits est réalisée tous les trimestres par les propriétaires de chaque système. Les anomalies détectées (droits excessifs, comptes orphelins) sont corrigées sous 5 jours ouvrés. Le rapport de revue est transmis au RSSI et archivé pendant 3 ans.

5. MESURES TECHNIQUES
- Annuaire centralisé Active Directory avec stratégies de groupe (GPO)
- Authentification SSO avec fédération SAML 2.0
- MFA obligatoire pour VPN, messagerie et applications critiques
- Journalisation de toutes les connexions dans le SIEM Splunk
- Délai de verrouillage : 5 tentatives échouées → verrouillage 30 minutes

6. INDICATEURS DE PERFORMANCE
KPI mensuel : taux de comptes actifs pour employés partis < 0,5% ; délai moyen de révocation < 24h ; couverture MFA > 99%.

Approuvé par : RSSI — Jean-Michel Bernard | DSI — Catherine Moreau | DG — Pierre Lefebvre
        """.strip(),
    },
    {
        'title': 'Procédure de gestion des incidents de sécurité',
        'theme': 'gestion_incidents',
        'text': """
Procédure de Gestion des Incidents de Sécurité — Réf : PROC-INC-2026-003 — Version 2.1 — Approuvée 20/01/2026

1. OBJECTIF
Définir le processus de détection, qualification, traitement et clôture des incidents de sécurité, conformément à ISO 27001 clause A.6.8 et au règlement DORA. Cette procédure garantit une réponse rapide et coordonnée minimisant l'impact sur la continuité d'activité.

2. CLASSIFICATION DES INCIDENTS
Niveau 1 — Critique : compromission confirmée, fuite de données, arrêt de service. Délai de réponse : 30 minutes. Escalade immédiate RSSI + DG + cellule de crise.
Niveau 2 — Majeur : tentative d'intrusion détectée, malware isolé, indisponibilité partielle. Délai : 2 heures. Escalade RSSI + DSI.
Niveau 3 — Mineur : phishing détecté, anomalie isolée, alerte SIEM sans impact confirmé. Délai : 24 heures. Traitement SOC niveau 1.

3. PROCESSUS DE TRAITEMENT
Phase 1 — Détection et signalement : l'incident est détecté via SIEM, signalé par un utilisateur ou remonté par un partenaire. Ouverture d'un ticket dans l'outil ITSM (ServiceNow) avec horodatage précis.
Phase 2 — Qualification : le SOC (Security Operations Center) évalue la criticité, l'étendue et les systèmes impactés dans les 30 minutes suivant la détection.
Phase 3 — Confinement : isolation des systèmes compromis, blocage des comptes suspects, révocation des tokens d'accès concernés.
Phase 4 — Éradication : suppression du malware, correction de la vulnérabilité exploitée, réinitialisation des mots de passe.
Phase 5 — Rétablissement : restauration des services depuis les dernières sauvegardes validées, tests de non-régression.
Phase 6 — Retour d'expérience (REX) : réunion post-incident obligatoire sous 5 jours. Rapport REX archivé. Mise à jour des procédures si nécessaire.

4. OBLIGATIONS RÉGLEMENTAIRES
Les incidents affectant des données personnelles doivent être notifiés à la CNIL dans les 72h (RGPD Art. 33). Les incidents critiques sont notifiés à l'ANSSI si l'organisation est OIV/OSE.

5. INDICATEURS
MTTD (Mean Time to Detect) cible : < 4h | MTTR (Mean Time to Respond) cible : < 8h | Taux de clôture sous SLA : > 95%

Validé par : RSSI | SOC Manager | Responsable Conformité
        """.strip(),
    },
    {
        'title': 'Plan de sauvegarde et de restauration',
        'theme': 'sauvegarde',
        'text': """
Plan de Sauvegarde et de Restauration — Réf : TECH-BCK-2026-007 — Version 4.0 — Approuvé 10/02/2026

1. PÉRIMÈTRE
Ce plan couvre l'ensemble des systèmes de production : serveurs d'application, bases de données, fichiers partagés, configurations réseau et données archivées. Il est révisé annuellement et testé trimestriellement.

2. OBJECTIFS DE RÉCUPÉRATION
RTO (Recovery Time Objective) : 4 heures pour les systèmes critiques, 24 heures pour les systèmes secondaires.
RPO (Recovery Point Objective) : 1 heure pour les bases de données critiques, 24 heures pour les fichiers bureautiques.

3. STRATÉGIE DE SAUVEGARDE
3.1 Sauvegardes quotidiennes : snapshot incrémentiel chiffré AES-256 à 02h00 chaque nuit. Rétention : 30 jours en ligne, 12 mois hors site.
3.2 Sauvegardes hebdomadaires : full backup complet chaque dimanche à 01h00. Rétention : 52 semaines.
3.3 Sauvegardes mensuelles : archive chiffrée stockée sur bande LTO-8. Rétention : 7 ans (conformité légale).
3.4 Réplication temps réel : bases de données critiques répliquées en mode synchrone vers le site DR (distance : 45 km).

4. CHIFFREMENT ET INTÉGRITÉ
Toutes les sauvegardes sont chiffrées avec AES-256. Les clés sont gérées via HashiCorp Vault. L'intégrité est vérifiée par hash SHA-256 et rapport automatique transmis au RSSI chaque matin.

5. TESTS DE RESTAURATION
Test mensuel sur environnement isolé : restauration d'une base de données critique avec validation de l'intégrité des données. Test trimestriel : restauration complète d'un serveur de production simulé avec chronométrage du RTO. Résultat du dernier test (15/03/2026) : RTO atteint en 2h47 — objectif respecté. PV de test archivé et signé par DSI.

6. RESPONSABILITÉS
Administrateur système senior : exécution et surveillance des sauvegardes. RSSI : validation des procédures et des tests. DG : approbation annuelle du plan.

Approuvé par : DSI — M. Rousseau | RSSI — J. Bernard | DG — P. Lefebvre
        """.strip(),
    },
    {
        'title': 'Politique de chiffrement des données',
        'theme': 'chiffrement',
        'text': """
Politique de Chiffrement des Données — Réf : PSI-CRYPT-2026-002 — Version 2.3 — Approuvée 05/04/2026

1. OBJET
Cette politique définit les standards de chiffrement applicables aux données de l'organisation, conformément à ISO 27001 clause A.8.24. Elle couvre les données en transit, au repos et en cours de traitement.

2. ALGORITHMES APPROUVÉS
Chiffrement symétrique : AES-256-GCM obligatoire pour les données classifiées CONFIDENTIEL et STRICTEMENT CONFIDENTIEL. AES-128 toléré pour les données internes standard.
Chiffrement asymétrique : RSA-4096 pour la signature et l'échange de clés. Courbes elliptiques ECDSA P-384 pour les certificats TLS.
Protocoles réseau : TLS 1.3 obligatoire. TLS 1.2 toléré jusqu'au 31/12/2026. TLS 1.0 et 1.1 interdits et bloqués par configuration.

3. GESTION DES CLÉS
3.1 Génération : les clés sont générées via HSM (Hardware Security Module) ou HashiCorp Vault selon la criticité.
3.2 Rotation : clés de session : rotation toutes les 24h. Clés de chiffrement de données : rotation annuelle. Clés de signature : rotation tous les 2 ans.
3.3 Stockage : aucune clé privée ne doit être stockée en clair. Coffre-fort Vault avec audit complet des accès.
3.4 Révocation : procédure d'urgence documentée permettant la révocation en moins d'1 heure.

4. APPLICATIONS ET SYSTÈMES CONCERNÉS
- Bases de données : chiffrement at-rest avec TDE (Transparent Data Encryption)
- Messagerie : signature S/MIME obligatoire pour les communications RH et juridiques
- Terminaux : chiffrement intégral des disques via BitLocker (Windows) ou LUKS (Linux)
- Cloud : chiffrement côté client avant tout upload sur services tiers

5. AUDIT ET CONFORMITÉ
Audit semestriel des certificats et clés par l'équipe sécurité. Rapport transmis au RSSI et au DPO. Renouvellement automatique des certificats via Let's Encrypt pour les services web internes.

Approuvé par : RSSI | Architecte sécurité | DPO
        """.strip(),
    },
    {
        'title': 'Procédure de journalisation et surveillance',
        'theme': 'journalisation',
        'text': """
Procédure de Journalisation et Surveillance — Réf : PROC-LOG-2026-005 — Version 3.1 — Approuvée 12/03/2026

1. OBJECTIF ET PÉRIMÈTRE
Cette procédure définit les exigences de collecte, stockage et analyse des journaux d'événements, conformément à ISO 27001 clause A.8.15. Elle couvre tous les systèmes connectés au réseau de l'organisation.

2. ÉVÉNEMENTS À JOURNALISER
Obligatoires : authentifications réussies et échouées, modifications de droits d'accès, accès aux données classifiées, démarrages et arrêts de services critiques, actions administrateurs, modifications de configuration.
Optionnels (selon niveau de criticité) : accès lecture aux données sensibles, trafic réseau anormal, erreurs applicatives critiques.

3. ARCHITECTURE DE COLLECTE
SIEM déployé : Splunk Enterprise Security. Agents installés sur 100% des serveurs de production. Transmission chiffrée via TLS 1.3 vers le collecteur central. Capacité de stockage : 12 mois en ligne (chaud), 7 ans en archive froide (conformité légale).

4. RÉTENTION ET INTÉGRITÉ
Les journaux sont stockés en lecture seule sur un stockage immuable (WORM). Un hash SHA-256 est calculé quotidiennement sur les fichiers de logs. Tout accès en modification déclenche une alerte critique. Aucun administrateur n'a accès en écriture aux archives.

5. SURVEILLANCE EN TEMPS RÉEL
Le SOC surveille les tableaux de bord 24/7. Alertes configurées pour : 5 tentatives de connexion échouées en 5 minutes, connexion hors plage horaire autorisée, accès depuis une IP non autorisée, exfiltration de données supérieure à 500 MB/heure.

6. REVUE ET AUDIT
Revue quotidienne des alertes critiques par le SOC. Rapport hebdomadaire au RSSI. Audit trimestriel de la politique de journalisation. Dernier audit : 10/03/2026 — Résultat : conforme, 3 actions d'amélioration identifiées et planifiées.

Approuvé par : RSSI | SOC Manager | DSI
        """.strip(),
    },
    {
        'title': 'Politique de gestion des fournisseurs',
        'theme': 'fournisseurs',
        'text': """
Politique de Gestion des Fournisseurs — Réf : PSI-FOUR-2026-004 — Version 1.8 — Approuvée 28/02/2026

1. OBJET
Cette politique encadre les relations avec les fournisseurs et prestataires qui accèdent aux systèmes, données ou locaux de l'organisation, conformément à ISO 27001 clauses A.5.19 à A.5.22.

2. CLASSIFICATION DES FOURNISSEURS
Niveau CRITIQUE : fournisseurs cloud, hébergeurs, opérateurs MPLS, intégrateurs SI avec accès root. Exigences : certification ISO 27001 ou SOC 2 Type II obligatoire, audit annuel, clause contractuelle de notification d'incident sous 24h.
Niveau IMPORTANT : fournisseurs de logiciels avec accès données, mainteneurs d'infrastructure. Exigences : questionnaire de sécurité annuel, NDA, clause RGPD.
Niveau STANDARD : fournisseurs sans accès SI ou données. Exigences : NDA standard, déclaration sur l'honneur sécurité.

3. PROCESSUS D'ÉVALUATION
Avant tout contrat : évaluation de sécurité basée sur ISO 27001 Annex A. Score minimum requis : 75/100. En dessous : mesures compensatoires obligatoires ou rejet.
Annuellement : réévaluation de tous les fournisseurs de niveau CRITIQUE et IMPORTANT. Rapport d'évaluation archivé 5 ans.

4. CLAUSES CONTRACTUELLES OBLIGATOIRES
Tous les contrats incluent : clause de confidentialité, clause RGPD (traitement des données personnelles), exigences de sécurité minimales, droit d'audit, obligation de notification d'incident dans les 24h, clause de réversibilité et portabilité des données.

5. REGISTRE DES FOURNISSEURS
Tenu à jour trimestriellement dans l'outil GRC. Actuellement : 47 fournisseurs actifs (12 CRITIQUES, 18 IMPORTANTS, 17 STANDARD). Dernier audit global : février 2026 — 44 fournisseurs conformes, 3 en plan d'action.

Approuvé par : RSSI | Directeur Achats | DPO
        """.strip(),
    },
]

ISO27001_NONCOMPLIANT_DOCS = [
    {
        'title': 'Gestion des accès — document incomplet',
        'theme': 'gestion_acces',
        'text': """
Note interne — Accès systèmes — Sans référence — Sans version — Non approuvé

Les accès aux systèmes sont accordés par le responsable informatique. Il n'y a pas de formulaire standard. Les demandes se font par email ou verbalement selon l'urgence. Plusieurs comptes administrateurs partagent le même mot de passe pour simplifier la gestion quotidienne.

La revue des accès n'est pas planifiée régulièrement. La dernière vérification remonte à 18 mois environ. Des comptes d'anciens employés restent actifs dans Active Directory car la procédure de clôture n'est pas systématiquement suivie lors des départs. Un audit informel a identifié 23 comptes orphelins en janvier dernier, mais leur suppression n'a pas encore été traitée.

L'authentification multi-facteurs n'est pas déployée sur les accès VPN. Les administrateurs utilisent uniquement un mot de passe simple. La politique de mot de passe autorise des mots de passe de 6 caractères minimum, sans complexité requise.

Aucune séparation des environnements de développement et de production n'est formalisée. Les développeurs ont accès direct à certaines bases de données de production pour les opérations de débogage. Cette pratique n'est pas documentée et présente un risque non évalué.

Il n'y a pas d'outil PAM déployé. Les sessions d'administration ne sont pas enregistrées. En cas d'incident, la traçabilité des actions administrateurs est insuffisante pour une investigation forensique. Ce point a été soulevé lors d'un audit externe en 2024 sans suite formelle.
        """.strip(),
    },
    {
        'title': 'Réponse aux incidents — procédure absente',
        'theme': 'gestion_incidents',
        'text': """
Mémo — Gestion des problèmes informatiques — Document de travail — Non validé — Juillet 2025

Quand quelque chose ne va pas sur le réseau ou les serveurs, les employés doivent appeler le support informatique au poste 4200 ou envoyer un mail à support@company.fr. Le support essaie de résoudre le problème le plus vite possible.

Il n'existe pas de procédure formelle distinguant les incidents de sécurité des incidents techniques ordinaires. En pratique, tout est traité de la même façon. Un incident de phishing subi en novembre 2024 (compromission de 3 comptes utilisateurs) a été géré de manière réactive sans documentation. Le rapport post-incident n'a jamais été rédigé.

L'équipe n'a pas de CSIRT (Computer Security Incident Response Team) constitué. Il n'y a pas de liste de contacts d'urgence formalisée. En dehors des heures ouvrées, personne n'est d'astreinte pour les incidents de sécurité. Le week-end précédent, une attaque par force brute a été détectée uniquement le lundi matin.

La notification RGPD n'est pas dans les réflexes : lors de l'incident de novembre, la CNIL n'a pas été notifiée bien que des données personnelles aient été potentiellement compromises. Ce manquement expose l'organisation à des sanctions.

Les métriques MTTD et MTTR ne sont pas mesurées. Il n'y a pas de tableau de bord de suivi des incidents. Aucun exercice de simulation n'a été réalisé. L'équipe ne s'est jamais entraînée à la réponse aux incidents. Le budget alloué à la sécurité opérationnelle est jugé insuffisant par le responsable IT.
        """.strip(),
    },
    {
        'title': 'Sauvegarde — pratiques non conformes',
        'theme': 'sauvegarde',
        'text': """
Document technique — Sauvegardes serveurs — Brouillon — Non relu — Janvier 2026

Les sauvegardes des serveurs sont effectuées par un script cron qui tourne chaque nuit. Le script copie les fichiers importants vers un NAS situé dans la même salle serveur. En cas d'incendie ou de dégât des eaux dans la salle, toutes les données seraient perdues simultanément.

Les sauvegardes ne sont pas chiffrées. Le NAS est accessible en lecture/écriture par tous les administrateurs. Un administrateur malveillant ou compromis pourrait modifier ou supprimer les sauvegardes. Aucune politique d'accès en lecture seule n'est en place.

La dernière restauration de test remonte à 14 mois. Entre-temps, le format des bases de données a été mis à jour. Il n'est pas certain que les anciennes sauvegardes soient restaurables dans le nouvel environnement. Personne n'a vérifié l'intégrité des fichiers de sauvegarde récemment.

Le RPO effectif est de 24h mais le script échoue silencieusement environ 2 fois par mois selon les logs consultés ad hoc. Il n'y a pas d'alerte configurée pour les échecs de sauvegarde. Un email d'alerte était prévu mais n'a jamais été implémenté.

Aucun plan de reprise d'activité (PRA) formel n'existe. En cas de sinistre majeur, le délai de rétablissement est estimé empiriquement à 3-5 jours mais n'a jamais été mesuré ni testé. La Direction n'a pas été informée de ces risques.
        """.strip(),
    },
    {
        'title': 'Chiffrement — absence de politique',
        'theme': 'chiffrement',
        'text': """
Note technique — Sécurité des communications — Sans approbation — Rédacteur : technicien réseau

Les communications internes utilisent HTTP pour plusieurs applications internes car la migration vers HTTPS n'a pas été priorisée. Le tableau de bord de monitoring, l'interface d'administration de la base de données et l'outil de déploiement sont accessibles en HTTP sur le réseau local.

Certains serveurs legacy utilisent encore TLS 1.0 pour assurer la compatibilité avec d'anciens clients. Cette configuration est connue pour être vulnérable aux attaques BEAST et POODLE mais aucune date de migration n'est planifiée.

Les bases de données de production ne sont pas chiffrées au repos. Les sauvegardes sur bande ne sont pas chiffrées. Des médias de sauvegarde ont été perdus lors d'un déménagement en 2023 — leur contenu n'était pas chiffré. Cet incident n'a pas fait l'objet d'une analyse de risque formelle.

Il n'existe pas de politique de chiffrement documentée. Les développeurs utilisent des algorithmes selon leurs préférences personnelles. Des mots de passe sont hashés en MD5 dans une application legacy, ce qui est notoirement insuffisant. La migration vers bcrypt est planifiée depuis 2 ans sans avancement.

La gestion des certificats SSL est manuelle. 3 certificats ont expiré l'année dernière sans que personne ne soit averti. Les utilisateurs ont vu des avertissements de sécurité dans leur navigateur pendant plusieurs semaines.
        """.strip(),
    },
    {
        'title': 'Journalisation insuffisante',
        'theme': 'journalisation',
        'text': """
Configuration logs systèmes — Note interne — Non datée — Non approuvée

La journalisation des événements de sécurité n'est pas centralisée. Chaque serveur conserve ses propres logs localement. La rétention varie de 7 jours à 3 mois selon les disques disponibles. Il n'y a pas de SIEM ni de collecteur central.

En pratique, les logs ne sont consultés qu'en cas de problème signalé. Il n'y a pas de surveillance proactive. Une tentative d'intrusion pourrait rester indétectée pendant plusieurs semaines. En janvier 2025, une analyse post-incident a révélé qu'un compte compromis avait été actif pendant 3 semaines sans détection.

Les actions des administrateurs ne sont pas toutes journalisées. L'utilisation du compte root sur les serveurs Linux ne génère pas d'alerte. Certaines applications métier ne produisent aucun log d'accès. Les connexions VPN sont journalisées mais les logs ne sont pas analysés.

La durée de rétention légale (1 an minimum selon la LPM pour les OIV) n'est pas respectée. Plusieurs serveurs ont des logs de moins de 3 mois. En cas d'enquête judiciaire, il serait impossible de reconstituer les événements au-delà de cette période.

Il n'y a pas d'alerte configurée pour les patterns d'attaque connus (brute force, privilege escalation, lateral movement). Les seuils d'alerte n'ont pas été définis. L'équipe n'a pas les outils pour distinguer un comportement anormal d'un comportement normal.
        """.strip(),
    },
    {
        'title': 'Fournisseurs sans encadrement sécurité',
        'theme': 'fournisseurs',
        'text': """
Liste des prestataires informatiques — Fichier Excel — Mis à jour irrégulièrement

Notre entreprise fait appel à de nombreux prestataires pour la maintenance et le développement. La liste n'est pas exhaustive car certains contrats sont signés directement par les directions métier sans validation DSI. On estime à une vingtaine le nombre de prestataires ayant accédé aux systèmes cette année.

Aucun questionnaire de sécurité n'est envoyé aux prestataires avant signature. La sécurité n'est pas un critère d'évaluation formalisé dans les appels d'offres. Un prestataire offshore travaille sur le code source de l'application principale sans avoir signé de NDA spécifique au code source.

Les accès accordés aux prestataires ne sont pas systématiquement révoqués à la fin des missions. Une analyse en mars 2026 a révélé que 8 comptes de prestataires terminés restaient actifs. Ces comptes avaient des droits d'accès aux environnements de développement et de qualification.

Les contrats ne comportent pas de clause de notification d'incident. Si un prestataire subit une violation de données impliquant les données de notre organisation, nous pourrions ne jamais être informés. Le RGPD exige pourtant une notification sous 72h.

Il n'y a pas de processus d'audit des prestataires. La dernière revue des accès tiers remonte à plus d'un an. Le registre des sous-traitants requis par le RGPD (article 30) n'est pas à jour.
        """.strip(),
    },
]


# ── TISAX — Documents réalistes ──────────────────────────────────────────────

TISAX_COMPLIANT_DOCS = [
    {
        'title': 'Plan de protection des informations prototypes',
        'theme': 'protection_prototypes',
        'text': """
Plan de Protection des Informations Prototypes — Réf : TISAX-PPP-2026-001 — Version 2.4 — Approuvé 15/02/2026

1. OBJET ET PÉRIMÈTRE
Ce plan définit les mesures de protection applicables aux informations et matériels de prototype automobile développés par notre bureau d'études, conformément aux exigences TISAX (Trusted Information Security Assessment Exchange) niveau AL2. Il s'applique à toutes les phases du cycle de développement : conception, maquette, prototypage, essais.

2. CLASSIFICATION DES INFORMATIONS PROTOTYPE
Niveau STRICTEMENT CONFIDENTIEL : données CAO des systèmes propulsion, architecture électronique véhicule, données de crash test, stratégies de contrôle moteur. Accès limité aux ingénieurs nommément autorisés sur liste nominative validée par le chef de projet.
Niveau CONFIDENTIEL : spécifications fonctionnelles, rapports d'essais intermédiaires, documents de liaison avec les équipementiers. Accès aux membres de l'équipe projet et partenaires accrédités TISAX.
Niveau INTERNE : procédures de travail, comptes-rendus de réunion, plannings. Accès à l'ensemble des collaborateurs du site.

3. CONTRÔLE DES ACCÈS PHYSIQUES
Le bureau d'études prototype est situé en zone sécurisée avec contrôle d'accès biométrique (empreinte digitale + badge). L'accès est limité au personnel nominativement autorisé. Les tentatives d'accès refusées sont journalisées et analysées quotidiennement. Les zones de stockage des maquettes physiques sont sous vidéosurveillance 24h/24 avec enregistrement conservé 90 jours.

4. CONTRÔLE DES ACCÈS NUMÉRIQUES
Les fichiers CAO sont stockés sur un serveur dédié isolé du réseau général. L'accès requiert une authentification double facteur. Tout transfert vers un support externe est interdit sauf dérogation signée par le Directeur Technique. Les fichiers prototypes sont marqués en filigrane numérique (watermark) permettant la traçabilité.

5. GESTION DES VISITEURS ET PARTENAIRES
Tout visiteur en zone prototype doit signer un accord de confidentialité spécifique avant l'entrée. Une escorte permanente est obligatoire. La photographie est interdite sauf autorisation explicite. Les partenaires équipementiers accédant aux données CAO doivent avoir obtenu leur accréditation TISAX et la transmettre avant tout partage.

6. AUDIT ET CONFORMITÉ
Audit interne semestriel des accès et des transferts. Revue annuelle de la liste des personnes autorisées. Dernier audit TISAX externe : janvier 2026 — score AL2 obtenu. Prochaine échéance : janvier 2028.

Approuvé par : Directeur R&D | RSSI | Chef de projet véhicule
        """.strip(),
    },
    {
        'title': 'Procédure de gestion des visiteurs en zone sensible',
        'theme': 'visiteurs',
        'text': """
Procédure de Gestion des Visiteurs — Réf : PROC-VIS-2026-002 — Version 3.0 — Approuvée 20/03/2026

1. OBJET
Cette procédure définit les règles d'accueil et d'accompagnement des visiteurs (clients, fournisseurs, partenaires, auditeurs) dans les zones sensibles du site industriel, conformément aux exigences TISAX et aux politiques de confidentialité de notre organisation.

2. TYPES DE VISITEURS ET NIVEAUX D'ACCÈS
Visiteurs PARTENAIRES ACCRÉDITÉS (TISAX AL1+) : accès aux zones de développement et salles de réunion projet. Escorte obligatoire. NDA spécifique projet signé préalablement.
Visiteurs CLIENTS : accès aux showrooms et zones de démonstration uniquement. Badge visiteur temporaire. Interdiction de la zone R&D.
Visiteurs INSTITUTIONNELS (auditeurs, autorités) : accès accompagné selon périmètre défini dans le mandat d'audit. Coordination avec RSSI avant visite.
Prestataires MAINTENANCE : accès uniquement aux zones d'intervention avec technicien interne accompagnateur. Accès révoqué dès fin d'intervention.

3. PROCESSUS D'ENREGISTREMENT
48h avant la visite : le responsable interne soumet la demande de visite via le portail RH. Vérification de l'habilitation TISAX pour les partenaires.
Jour de la visite : présentation d'une pièce d'identité à l'accueil. Signature du registre des visiteurs et de l'accord de confidentialité. Attribution d'un badge visiteur temporaire avec photo, horodaté et coloré selon le niveau d'accès autorisé.
Pendant la visite : escorte permanente obligatoire. Interdiction de photographier en zones sensibles. Les téléphones doivent rester en poche dans les zones prototypes.
Fin de visite : restitution obligatoire du badge à l'accueil. Enregistrement de l'heure de départ. Le badge non restitué déclenche une alerte sécurité.

4. REGISTRE DES VISITES
Tenu informatiquement dans le système de contrôle d'accès. Conservé 5 ans. Accessible au RSSI et à la Direction. Exportable pour les audits TISAX. Dernière revue : mars 2026 — 847 visites enregistrées, 0 anomalie.

Approuvé par : Responsable Sécurité Site | RSSI | Direction Générale
        """.strip(),
    },
    {
        'title': 'Politique de sécurité physique des locaux',
        'theme': 'securite_physique',
        'text': """
Politique de Sécurité Physique — Réf : PSI-PHY-2026-003 — Version 2.1 — Approuvée 10/01/2026

1. PÉRIMÈTRE DE SÉCURITÉ
Le site industriel est structuré en zones concentriques de sécurité croissante :
Zone 0 — Publique : parking visiteurs, hall d'accueil. Accès libre avec contrôle visuel.
Zone 1 — Bureaux administratifs : badge RFID obligatoire. Accès à tous les employés.
Zone 2 — Ateliers de production : badge + code PIN. Accès au personnel production et maintenance.
Zone 3 — Bureau d'études et R&D : biométrie (empreinte digitale) + badge. Liste nominative. Vidéosurveillance.
Zone 4 — Salle prototypes et archive sécurisée : biométrie + double badge (responsable + occupant). Accès ultra-restreint. Cage de Faraday pour les données RF.

2. CONTRÔLE D'ACCÈS PHYSIQUE
Lecteurs biométriques de dernière génération sur toutes les entrées de Zone 3 et 4. Enregistrement horodaté de chaque accès et tentative. Révocation instantanée en cas de départ ou suspension. Anti-tailgating (sas double porte) sur l'entrée principale Zone 3.

3. VIDÉOSURVEILLANCE
Couverture totale des Zones 3 et 4. Enregistrement continu 24h/24, 7j/7. Rétention 90 jours. Consultation sur autorisation du RSSI ou direction. Signalisation réglementaire RGPD en place. Caméras infrarouges pour vision nocturne.

4. PROTECTION CONTRE LES MENACES PHYSIQUES
Armoires de sécurité grade 4 pour les supports de stockage contenant des données classifiées. Broyeur de documents classe P-4 (coupe croisée) dans chaque bureau R&D. Politique clean desk : bureau dégagé obligatoire en fin de journée. Vérification par rondes de sécurité nocturnes. Aucun document prototype papier ne doit quitter le site sans autorisation signée.

5. MAINTENANCE ET TESTS
Test mensuel des accès d'urgence. Vérification semestrielle des caméras et lecteurs. Rapport annuel au RSSI. Dernier rapport physique : 28/02/2026 — conformité 98%, 1 lecteur remplacé suite à défaillance détectée.

Approuvé par : Responsable Sécurité Site | RSSI | Direction
        """.strip(),
    },
    {
        'title': 'Contrôle des accès réseau et cloisonnement',
        'theme': 'acces_reseau',
        'text': """
Architecture Réseau Sécurisée — Réf : ARCH-NET-2026-004 — Version 4.2 — Approuvée 05/03/2026

1. ARCHITECTURE DE SEGMENTATION
Le réseau du site est segmenté en VLAN distincts et isolés conformément aux exigences TISAX AL2 :
VLAN 10 — Production IT : ERP, messagerie, outils bureautiques. Accès internet filtré.
VLAN 20 — R&D Prototype : serveurs CAO, outils de simulation, bancs de test. AUCUN accès internet direct. Flux sortants via proxy applicatif avec inspection de contenu.
VLAN 30 — OT/Atelier : équipements de production, automates. Isolation totale du réseau IT.
VLAN 40 — Visiteurs/Invités : accès internet uniquement. Séparé de tous les VLANs internes.
VLAN 50 — Administration : gestion réseau, outils de supervision. Accès limité aux administrateurs.

2. CONTRÔLE DES ACCÈS RÉSEAU
802.1X déployé sur tous les switchs. Authentification par certificat machine avant tout accès. Aucun équipement non enregistré ne peut se connecter. NAC (Network Access Control) avec quarantaine automatique des équipements non conformes (absence de patch, antivirus expiré).

3. FILTRAGE ET INSPECTION
Pare-feu de nouvelle génération (Palo Alto PA-5250) avec inspection SSL. Règles de filtrage basées sur l'identité (utilisateur + machine). IDS/IPS avec signatures mises à jour quotidiennement. DLP (Data Loss Prevention) sur les flux sortants du VLAN R&D : détection et blocage des fichiers CAO.

4. ACCÈS DISTANTS
VPN IPsec IKEv2 avec MFA obligatoire pour le télétravail. Session VPN limitée à 8h avec renouvellement d'authentification. Tunnel split interdit : tout le trafic passe par le VPN. Accès distant au VLAN R&D soumis à une autorisation nominative du RSSI.

5. JOURNALISATION
Tous les flux inter-VLAN sont journalisés dans le SIEM. Alertes configurées pour les tentatives d'accès VLAN 20 depuis VLAN 40. Rapport mensuel de topologie réseau soumis au RSSI.

Approuvé par : Architecte réseau | RSSI | DSI
        """.strip(),
    },
]

TISAX_NONCOMPLIANT_DOCS = [
    {
        'title': 'Accès zone prototype sans contrôle formalisé',
        'theme': 'protection_prototypes',
        'text': """
Note de service — Accès aux ateliers — Rédigée par chef d'atelier — Non datée — Non approuvée

L'accès aux ateliers prototype se fait avec le badge habituel. Tout le monde ayant un badge de l'entreprise peut techniquement entrer dans la zone de développement. Il n'y a pas de liste nominative des personnes autorisées. On fait confiance aux employés pour ne pas entrer dans des zones qui ne les concernent pas.

Les fichiers de conception sont stockés sur un serveur partagé accessible à l'ensemble du réseau de l'entreprise. Le dossier prototype n'a pas de restriction d'accès particulière. Les développeurs utilisent le même accès réseau que les comptables ou les RH. Un contrôle d'accès avait été proposé l'année dernière mais n'a pas été mis en place faute de budget.

Les partenaires équipementiers reçoivent les fichiers CAO par email. L'email n'est pas chiffré. Certains partenaires n'ont pas fourni leur certification TISAX mais ont quand même reçu des fichiers confidentiels car le projet ne pouvait pas attendre. Il n'y a pas de watermark sur les fichiers partagés.

Lors d'une visite client en décembre 2025, un représentant a pris des photos dans la zone de développement avec son téléphone portable. Le technicien qui l'accompagnait n'a pas signalé l'incident car il ne savait pas que c'était interdit. Le règlement intérieur ne mentionne pas explicitement l'interdiction de photographier.

Il n'y a pas d'audit TISAX en cours. La Direction n'a pas décidé de demander une accréditation TISAX bien que plusieurs clients automobiles l'exigent contractuellement. Cela bloque actuellement 2 contrats potentiels.
        """.strip(),
    },
    {
        'title': 'Gestion visiteurs informelle sans traçabilité',
        'theme': 'visiteurs',
        'text': """
Accueil visiteurs — Procédure informelle — Rédigée par hôtesse d'accueil — 2024

Quand des visiteurs arrivent, on leur demande de signer le cahier à l'accueil. Parfois on oublie si c'est chargé. Le cahier papier est stocké dans le tiroir du bureau d'accueil. Il n'est pas conservé de manière structurée. Les anciens cahiers sont parfois jetés quand ils sont pleins.

Les visiteurs ne signent pas systématiquement d'accord de confidentialité. On leur donne parfois une fiche à signer mais ce n'est pas toujours disponible. Certains visiteurs techniques sont escortés, d'autres non selon la disponibilité des personnes internes.

Des prestataires de nettoyage ont accès aux bureaux en dehors des heures ouvrables. Ils ont des clés physiques mais pas de badge électronique, donc leurs passages ne sont pas tracés. Il n'y a pas d'inventaire des clés distribuées. Une clé a été perdue en 2024 sans que la serrure soit changée.

Des badges visiteurs ont été perdus. On ne sait pas combien ont été égarés. Le système de badges n'a pas de date d'expiration automatique. Théoriquement, un badge visiteur perdu pourrait permettre l'accès au site pendant des semaines. On a récemment trouvé un badge visiteur datant de 2022 dans une salle de réunion.

La zone R&D n'a pas de contrôle d'accès différencié. Le même badge ouvre les bureaux administratifs et les ateliers techniques. Il n'y a pas de vidéosurveillance dans la zone de prototypage. En cas d'incident, il serait impossible de savoir qui était présent.
        """.strip(),
    },
    {
        'title': 'Sécurité physique insuffisante',
        'theme': 'securite_physique',
        'text': """
État des lieux sécurité physique — Document interne — Non validé — Rédacteur anonyme

Le site n'a pas de périmètre de sécurité clairement défini. Les zones sensibles ne sont pas matérialisées. Les employés ne savent pas toujours ce qui est considéré comme confidentiel. Il n'y a pas de signalétique de zone ni de procédure d'urgence affichée.

La politique clean desk n'est pas respectée. Lors d'une tournée informelle des bureaux à 18h, 12 postes de travail avaient des documents laissés visibles, dont certains marqués CONFIDENTIEL. Les écrans d'ordinateur ne se verrouillent pas automatiquement avant 30 minutes d'inactivité. Plusieurs ingénieurs R&D n'ont jamais activé le chiffrement de leur poste.

Il n'y a pas de broyeur de documents dans les bureaux R&D. Les documents de conception sont jetés dans la corbeille ordinaire ou le bac de recyclage sans destruction préalable. Des concurrents pourraient théoriquement récupérer des informations dans les poubelles du site (dumpster diving).

La salle serveur est accessible avec un badge standard. Elle n'a pas de contrôle d'accès renforcé. Les prestataires de maintenance serveur n'ont pas besoin de demander un accès spécial. La liste des personnes ayant accès à la salle serveur n'est pas tenue à jour. Le registre papier collé sur la porte est incomplet.

Aucun audit de sécurité physique n'a été réalisé dans les 3 dernières années. Le dernier rapport de sécurité remonte à 2023 et les actions recommandées n'ont été que partiellement mises en œuvre. Le budget sécurité physique a été réduit de 30% lors du dernier exercice.
        """.strip(),
    },
    {
        'title': 'Réseau non segmenté avec accès non contrôlé',
        'theme': 'acces_reseau',
        'text': """
Infrastructure réseau — Note technique — Technicien réseau junior — Non validée

Le réseau de l'entreprise est un réseau plat (flat network). Tous les équipements sont sur le même sous-réseau /16. Les postes de travail des développeurs R&D, les serveurs de production et les équipements visiteurs sont tous accessibles les uns des autres sans restriction. Cette architecture facilitait la gestion au départ mais présente des risques croissants.

Il n'y a pas de segmentation entre le réseau OT (automates de production) et le réseau IT. En théorie, un poste de travail compromis pourrait envoyer des commandes aux automates. Cela n'est pas arrivé à notre connaissance mais le risque est réel.

L'authentification 802.1X n'est pas déployée. Toute prise réseau accessible peut être utilisée par n'importe quel équipement. Lors d'un test informel, un consultant externe a pu connecter son ordinateur personnel sur une prise de la salle de réunion et accéder aux partages réseau internes. Cet incident n'a pas été formellement traité.

Le WiFi visiteurs utilise le même SSID et la même clé WPA2 depuis 3 ans. La clé n'a jamais été changée. D'anciens prestataires connaissent encore cette clé. Le réseau WiFi visiteurs n'est pas isolé du réseau interne : des VLAN sont partiellement configurés mais plusieurs équipements contournent cette segmentation.

Il n'y a pas de DLP. Les employés peuvent copier des fichiers de conception sur des clés USB personnelles. Un cas de fuite de données non confirmé a été signalé en 2025 mais aucune investigation n'a été menée. Le pare-feu périmétrique est configuré avec des règles permissives héritées et jamais révisées.
        """.strip(),
    },
]


# ── Shared reviewer comments ─────────────────────────────────────────────────

REVIEWER_OK = [
    "Document conforme aux exigences. Toutes les sections requises sont présentes et à jour.",
    "Validation satisfaisante. La politique est approuvée, versionnée et accessible aux parties prenantes.",
    "Conformité vérifiée lors de la revue du {date}. Les preuves d'implémentation sont disponibles.",
    "Excellent niveau de documentation. Les procédures sont claires, testées et les responsabilités définies.",
    "Approuvé. Le document respecte intégralement les exigences de la norme. Prochaine revue planifiée.",
    "Contrôle conforme. Les indicateurs de performance sont définis et mesurés régulièrement.",
]

REVIEWER_NOK = [
    "Non-conformité identifiée. Le document manque d'approbation formelle et de versioning.",
    "Insuffisant. Les procédures décrites ne sont pas effectivement implémentées selon les preuves collectées.",
    "Rejeté. L'absence de tests réguliers et de métriques rend ce document non conforme.",
    "Non conforme. Les responsabilités ne sont pas clairement assignées et les délais non respectés.",
    "Document inadéquat. Les risques identifiés ne sont pas traités et les mesures compensatoires absentes.",
    "Validité expirée. Le document n'a pas été révisé depuis plus d'un an sans justification.",
]


def _pick_reviewer_comment(is_ok: bool) -> str:
    import random
    from datetime import date
    template = random.choice(REVIEWER_OK if is_ok else REVIEWER_NOK)
    today = date.today()
    return template.format(date=today.strftime('%d/%m/%Y'))


# ── Main command class ────────────────────────────────────────────────────────

NORM_KEY_MAP = [
    ('9001', 'ISO9001'),
    ('27001', 'ISO27001'),
    ('tisax', 'TISAX'),
]


def _norm_key(norm_name: str) -> str:
    n = norm_name.lower().replace(' ', '').replace('-', '')
    for fragment, key in NORM_KEY_MAP:
        if fragment in n:
            return key
    return None


class Command(BaseCommand):
    help = 'Generate high-quality realistic ML datasets for ISO 27001 and TISAX.'

    def add_arguments(self, parser):
        parser.add_argument('--norm', type=str, default='all',
                            help='ISO27001 | TISAX | all')
        parser.add_argument('--count', type=int, default=500,
                            help='Total documents to generate (default 500)')
        parser.add_argument('--seed', type=int, default=2026)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        import random
        random.seed(options['seed'])
        dry = options['dry_run']
        target_norm = options['norm'].upper()
        count = options['count']

        self.stdout.write(self.style.SUCCESS('=== GENERATE REALISTIC DATASETS ===\n'))

        norms = Norme.objects.all()
        for norm in norms:
            key = _norm_key(norm.name)
            if target_norm != 'ALL' and key != target_norm:
                continue
            if key not in ('ISO27001', 'TISAX'):
                self.stdout.write(f'  [{norm.name}] Skipping — only ISO27001 and TISAX supported\n')
                continue

            if key == 'ISO27001':
                compliant_pool = ISO27001_COMPLIANT_DOCS
                noncompliant_pool = ISO27001_NONCOMPLIANT_DOCS
            else:
                compliant_pool = TISAX_COMPLIANT_DOCS
                noncompliant_pool = TISAX_NONCOMPLIANT_DOCS

            half = count // 2
            self.stdout.write(f'  [{norm.name}] Generating {half} approved + {half} rejected...')

            if dry:
                self.stdout.write(f'    DRY RUN — would create {count} documents\n')
                continue

            created = self._generate_for_norm(norm, compliant_pool, noncompliant_pool, half)
            self.stdout.write(self.style.SUCCESS(f'    Created {created} training records\n'))

        self.stdout.write('=== DATASET GENERATION COMPLETE ===')
        self.stdout.write('Now run: python manage.py retrain_all_models')

    def _generate_for_norm(self, norm, compliant_pool, noncompliant_pool, half_count):
        import random
        from django.db.models.signals import post_save
        from api import signals as api_signals

        rules = list(norm.rules.order_by('id'))
        n_rules = len(rules)
        created = 0

        # Disconnect signal to avoid double TrainingSample creation
        post_save.disconnect(api_signals.create_training_sample_on_validation, sender=Validation)

        try:
            for idx in range(half_count * 2):
                is_approved = idx < half_count
                label = 'approved' if is_approved else 'rejected'
                pool = compliant_pool if is_approved else noncompliant_pool
                doc_template = pool[idx % len(pool)]

                # Vary text slightly to avoid exact duplicates
                doc_text = doc_template['text']
                variation_suffix = f"\n\nRéférence interne : {norm.name[:6].upper()}-{idx+1:04d}-{label[:3].upper()}"
                # Add realistic noise phrases (25% chance) to reduce perfect separability
                noise_ok = [
                    "\n\nNote de revue : quelques points mineurs à améliorer lors du prochain audit.",
                    "\n\nObservation : un retard ponctuel a été observé mais rapidement corrigé.",
                ]
                noise_nok = [
                    "\n\nNote : certaines sections présentent des éléments partiellement conformes.",
                    "\n\nObservation : des efforts ont été entrepris mais restent insuffisants.",
                ]
                if random.random() < 0.25:
                    variation_suffix += random.choice(noise_ok if is_approved else noise_nok)
                doc_text_full = doc_text + variation_suffix

                # Create Document
                with transaction.atomic():
                    doc = Document.objects.create(
                        file=f'realistic/{_norm_key(norm.name)}/{label}/doc_{idx+1:04d}.pdf',
                        norme=norm,
                        employee_username=random.choice([
                            'alice.martin', 'bob.dupont', 'claire.bernard',
                            'david.petit', 'emma.robert', 'francois.simon',
                        ]),
                        employee_department=random.choice(['SECURITE', 'DSI', 'QUALITE', 'DIRECTION']),
                        teamlead_username='teamlead_realistic',
                        status=label,
                        final_decision=label,
                        decision_reason=f'Document {label} — {doc_template["theme"]} — évaluation réaliste.',
                        reviewer_comment=_pick_reviewer_comment(is_approved),
                        approved_by='teamlead_realistic',
                        approved_at=timezone.now(),
                        review_completed_at=timezone.now(),
                        is_finalized=True,
                    )

                    # Build rule results based on compliance
                    if is_approved:
                        valid_count = random.randint(max(1, n_rules * 7 // 10), n_rules)
                    else:
                        valid_count = random.randint(0, max(0, n_rules * 4 // 10))

                    shuffled_rules = list(rules)
                    random.shuffle(shuffled_rules)
                    valid_rule_ids = set(r.id for r in shuffled_rules[:valid_count])

                    rule_results = {}
                    features = {}
                    approved_rule_names = []
                    rejected_rule_names = []
                    fvector = []

                    for rule in rules:
                        is_valid = rule.id in valid_rule_ids
                        rule_results[rule.title] = 1 if is_valid else 0
                        features[rule.title] = 1 if is_valid else 0
                        fvector.append(1 if is_valid else 0)
                        if is_valid:
                            approved_rule_names.append(rule.title)
                        else:
                            rejected_rule_names.append(rule.title)

                        # Evidence text = excerpt from the document text (realistic)
                        words = doc_text.split()
                        excerpt_start = random.randint(0, max(0, len(words) - 30))
                        excerpt = ' '.join(words[excerpt_start:excerpt_start + random.randint(15, 35)])

                        if is_valid:
                            ev_text = f"[{rule.title}] Conforme : {excerpt}"
                        else:
                            ev_text = f"[{rule.title}] Non conforme : {excerpt} — mesure manquante ou insuffisante."

                        Validation.objects.create(
                            document=doc,
                            rule=rule,
                            teamlead_username='teamlead_realistic',
                            evidence_text=ev_text,
                            is_valid=is_valid,
                            comment=_pick_reviewer_comment(is_valid),
                        )

                        rts_label = 'approved' if is_valid else 'rejected'
                        RuleTrainingSample.objects.create(
                            document=doc,
                            norm=norm,
                            rule=rule,
                            rule_title=rule.title,
                            rule_description=rule.description or '',
                            evidence_text=ev_text,
                            reviewer_comment=_pick_reviewer_comment(is_valid),
                            recommendation='Maintenir la conformité.' if is_valid else 'Mettre en œuvre les mesures correctives sous 30 jours.',
                            label=rts_label,
                            final_document_decision=label,
                            confidence_score=round(random.uniform(0.72, 0.96) if is_valid else random.uniform(0.55, 0.85), 2),
                            semantic_score=round(random.uniform(0.68, 0.94) if is_valid else random.uniform(0.50, 0.80), 2),
                        )

                    compliance_score = round(valid_count / max(n_rules, 1) * 100, 1)

                    # TrainingSample WITH full text fields populated
                    TrainingSample.objects.update_or_create(
                        document=doc,
                        defaults={
                            'norm_id': norm.id,
                            'features': features,
                            'feature_vector': fvector,
                            'label': label,
                            'standard': norm.name,
                            'teamlead_decision': label,
                            'final_decision': label,
                            'decision_reason': _pick_reviewer_comment(is_approved),
                            'approved': is_approved,
                            'total_rules': n_rules,
                            'valid_rules_count': valid_count,
                            'invalid_rules_count': n_rules - valid_count,
                            'approved_rules': approved_rule_names,
                            'rejected_rules': rejected_rule_names,
                            'rule_results_json': rule_results,
                            'compliance_score': compliance_score,
                            'confidence_score': round(compliance_score / 100.0, 2),
                            # KEY: populate text fields
                            'document_text': doc_text_full[:3000],
                            'evidence_text': ' | '.join([
                                f"[{r.title}]: {'OK' if r.id in valid_rule_ids else 'NOK'}"
                                for r in rules
                            ]),
                            'rule_text': ' | '.join([r.title for r in rules]),
                        }
                    )
                    created += 1

        finally:
            post_save.connect(api_signals.create_training_sample_on_validation, sender=Validation)

        return created
