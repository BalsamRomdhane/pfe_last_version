"""
Management command: generate_iso27001_tisax_datasets

Generates realistic synthetic training data for ISO 27001 and TISAX norms.
Creates RuleTrainingSample rows with realistic French enterprise evidence texts.

Usage:
    python manage.py generate_iso27001_tisax_datasets
    python manage.py generate_iso27001_tisax_datasets --norm ISO27001 --samples 300
    python manage.py generate_iso27001_tisax_datasets --norm TISAX --samples 300
"""
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import Norme, Rule, RuleTrainingSample, TrainingSample, Document

# ── ISO 27001 Rules ──────────────────────────────────────────────────────────
ISO27001_RULES = [
    {
        'title': 'Gestion des accès et des identités',
        'description': 'Les accès aux systèmes doivent être contrôlés via un système IAM avec authentification forte.',
        'severity': 'CRITICAL',
        'evidence': {
            True: [
                "Système IAM Okta déployé avec MFA obligatoire sur tous les comptes privilégiés.",
                "Revue trimestrielle des droits d'accès réalisée le 15/04/2026, 12 comptes révoqués.",
                "Politique de moindre privilège appliquée, revue accès documentée et signée par RSSI.",
                "Active Directory configuré avec groupes de sécurité, accès approuvés par manager.",
            ],
            False: [
                "Comptes partagés détectés sur 3 serveurs de production sans traçabilité individuelle.",
                "Aucun processus de revue des droits d'accès, des comptes anciens employés restent actifs.",
                "MFA non configuré sur les comptes administrateurs de la base de données.",
                "Accès root partagé entre 5 techniciens sans journalisation des actions.",
            ],
        },
    },
    {
        'title': 'Journalisation et surveillance',
        'description': 'Tous les événements de sécurité doivent être journalisés et surveillés en temps réel.',
        'severity': 'HIGH',
        'evidence': {
            True: [
                "SIEM Splunk opérationnel, alertes configurées pour détection d'intrusion en temps réel.",
                "Logs conservés 12 mois sur stockage chiffré, revue hebdomadaire des alertes critiques.",
                "Tableau de bord SOC actif, 3 incidents détectés et traités en Q1 2026.",
                "Journalisation centralisée via ELK Stack, rétention 365 jours, intégrité vérifiée.",
            ],
            False: [
                "Logs système désactivés sur les serveurs web depuis la migration de novembre 2025.",
                "Aucun outil SIEM déployé, les journaux ne sont pas centralisés ni analysés.",
                "Rétention des logs de 7 jours seulement, non conforme à la politique de 12 mois.",
                "Alertes de sécurité non configurées, incidents détectés uniquement par les utilisateurs.",
            ],
        },
    },
    {
        'title': 'Sauvegarde et restauration',
        'description': 'Les sauvegardes doivent être régulières, chiffrées et testées régulièrement.',
        'severity': 'HIGH',
        'evidence': {
            True: [
                "Sauvegardes quotidiennes chiffrées AES-256, test de restauration réussi le 10/05/2026.",
                "Plan de reprise d'activité testé annuellement, RTO de 4h validé en conditions réelles.",
                "Sauvegardes hors site synchronisées toutes les 6h, RPO de 6h respecté.",
                "Procédure de backup documentée, dernière restauration test le 20/04/2026 sans erreur.",
            ],
            False: [
                "Sauvegardes non chiffrées stockées sur le même site que la production.",
                "Aucun test de restauration réalisé depuis 18 mois, intégrité des backups non vérifiée.",
                "Sauvegardes hebdomadaires uniquement, RPO de 7 jours non conforme aux exigences.",
                "Script de backup en erreur depuis le 01/03/2026, aucune alerte configurée.",
            ],
        },
    },
    {
        'title': 'Chiffrement des données sensibles',
        'description': 'Les données sensibles doivent être chiffrées en transit et au repos.',
        'severity': 'CRITICAL',
        'evidence': {
            True: [
                "TLS 1.3 enforced sur toutes les APIs, certificats renouvelés automatiquement via Let's Encrypt.",
                "Bases de données chiffrées avec AES-256, clés gérées via HashiCorp Vault.",
                "Données personnelles chiffrées au repos, politique de gestion des clés documentée.",
                "Chiffrement de bout en bout activé pour les communications internes sensibles.",
            ],
            False: [
                "API REST accessible en HTTP sans redirection vers HTTPS, données en clair en transit.",
                "Base de données client non chiffrée, mots de passe stockés en MD5.",
                "Données de sauvegarde non chiffrées sur le NAS partagé accessible au réseau.",
                "TLS 1.0 encore actif sur 2 serveurs legacy, vulnérable à POODLE/BEAST.",
            ],
        },
    },
    {
        'title': 'Gestion des incidents de sécurité',
        'description': 'Un processus formalisé de gestion des incidents doit être en place et testé.',
        'severity': 'HIGH',
        'evidence': {
            True: [
                "Processus ITIL de gestion incidents documenté, équipe CSIRT disponible 24/7.",
                "5 incidents de sécurité traités en Q1 2026, délai moyen de résolution : 4h.",
                "Exercice de simulation d'incident réalisé le 12/03/2026, rapport disponible.",
                "Playbooks d'incident créés pour 8 scénarios critiques, testés trimestriellement.",
            ],
            False: [
                "Aucune procédure formalisée de gestion des incidents, réponse ad hoc uniquement.",
                "Incident de fuite de données en janvier non documenté, aucune notification client.",
                "Équipe de réponse aux incidents non formée, pas de contact CSIRT identifié.",
                "Délai moyen de détection des incidents : 72h, non conforme à l'objectif de 4h.",
            ],
        },
    },
    {
        'title': 'Sécurité des fournisseurs et tiers',
        'description': 'Les fournisseurs accédant aux systèmes doivent être évalués et contractualisés.',
        'severity': 'MEDIUM',
        'evidence': {
            True: [
                "Questionnaires de sécurité envoyés à 18 fournisseurs, 16 validés en 2026.",
                "Clauses RGPD et sécurité intégrées dans tous les contrats fournisseurs depuis 01/2025.",
                "Audit annuel des fournisseurs critiques, dernier audit réalisé le 05/04/2026.",
                "Registre des tiers mis à jour trimestriellement, accès VPN fournisseurs tracés.",
            ],
            False: [
                "Aucun contrat de traitement des données signé avec le prestataire cloud principal.",
                "Fournisseurs accédant au réseau interne sans évaluation préalable de sécurité.",
                "Pas de registre des accès tiers, impossible d'auditer les connexions externes.",
                "Sous-traitant offshore sans clause de confidentialité ni engagement ISO 27001.",
            ],
        },
    },
    {
        'title': 'Continuité d\'activité',
        'description': 'Un plan de continuité d\'activité (PCA) doit être maintenu et testé.',
        'severity': 'MEDIUM',
        'evidence': {
            True: [
                "PCA documenté, approuvé par la Direction, test annuel réalisé en mars 2026.",
                "BIA réalisé en 2025, processus critiques identifiés avec RTO/RPO définis.",
                "Site de repli opérationnel à 120km, basculement testé avec succès le 15/02/2026.",
                "Formation continuité assurée pour 45 collaborateurs clés, exercice tabletop Q1 2026.",
            ],
            False: [
                "PCA rédigé en 2020, jamais mis à jour ni testé depuis.",
                "Aucun site de repli identifié, continuité non assurée en cas de sinistre.",
                "BIA non réalisé, priorités de reprise non définies par la Direction.",
                "Exercice de reprise annulé 2 années consécutives faute de budget.",
            ],
        },
    },
    {
        'title': 'Sensibilisation et formation sécurité',
        'description': 'Tous les employés doivent recevoir une formation sécurité annuelle.',
        'severity': 'MEDIUM',
        'evidence': {
            True: [
                "Formation phishing annuelle réalisée, taux de clic réduit de 18% à 4% en 2026.",
                "E-learning sécurité obligatoire, 97% des collaborateurs ont validé le module.",
                "Campagne de sensibilisation mensuelle, affichages et newsletters diffusés.",
                "Programme onboarding sécurité pour nouveaux arrivants, quiz de validation inclus.",
            ],
            False: [
                "Aucune formation sécurité dispensée en 2025 et 2026 faute de budget.",
                "Taux de clic phishing simulé de 42%, indicateur de manque de sensibilisation.",
                "Formation sécurité optionnelle, seulement 23% des employés formés.",
                "Onboarding sécurité inexistant, nouveaux employés non sensibilisés aux politiques.",
            ],
        },
    },
]

# ── TISAX Rules ──────────────────────────────────────────────────────────────
TISAX_RULES = [
    {
        'title': 'Sécurité physique des locaux',
        'description': 'Les locaux doivent être protégés par des contrôles d\'accès physiques adaptés.',
        'severity': 'CRITICAL',
        'evidence': {
            True: [
                "Contrôle d'accès biométrique installé sur les zones de développement prototype.",
                "Journal des accès physiques conservé 12 mois, revue mensuelle réalisée.",
                "Caméras de surveillance couvrant 100% des zones sensibles, enregistrement 30j.",
                "Sas d'entrée avec double validation badge+code, anti-tailgating opérationnel.",
            ],
            False: [
                "Accès aux bureaux R&D protégé uniquement par un badge non traçable.",
                "Aucune caméra dans la zone de stockage des prototypes automobiles.",
                "Visiteurs accédant aux zones sensibles sans escorte ni enregistrement.",
                "Serrures mécaniques sans journalisation sur 4 salles de conception.",
            ],
        },
    },
    {
        'title': 'Gestion des visiteurs et des accès externes',
        'description': 'Les visiteurs doivent être enregistrés et escortés dans les zones sensibles.',
        'severity': 'HIGH',
        'evidence': {
            True: [
                "Registre des visiteurs tenu avec photo, signature NDA, badge visiteur tracé.",
                "Processus d'accueil visiteur formalisé, escorte obligatoire en zone protégée.",
                "Accès visiteurs révoqués dans les 24h après la visite, log conservé.",
                "Formation escorte dispensée à 100% du personnel d'accueil, procédure affichée.",
            ],
            False: [
                "Registre des visiteurs incomplet, 30% des visites non enregistrées en avril.",
                "Visiteurs laissés sans escorte dans les couloirs de l'atelier de prototypes.",
                "Badge visiteur non récupéré à la sortie dans 5 cas identifiés en mars 2026.",
                "NDA non signé par 2 prestataires ayant accédé aux zones de développement.",
            ],
        },
    },
    {
        'title': 'Protection des informations de prototype',
        'description': 'Les données techniques des véhicules doivent être classifiées et protégées.',
        'severity': 'CRITICAL',
        'evidence': {
            True: [
                "Classification des données prototypes appliquée : Confidentiel/Secret/Public.",
                "CAO chiffrée sur poste de travail, transfert uniquement via canal sécurisé approuvé.",
                "Politique de clean desk respectée à 100%, vérifiée lors de l'audit du 05/05/2026.",
                "Documents prototypes watermarqués et tracés, DRM appliqué aux fichiers CAD.",
            ],
            False: [
                "Plans techniques partagés via email non chiffré à des partenaires non TISAX.",
                "Aucune classification des données prototypes, tout document traité identiquement.",
                "Fichiers CAO sur clé USB non chiffrée retrouvée en salle de réunion commune.",
                "Clean desk non appliqué, plans de prototype visibles sur 3 bureaux pendant l'audit.",
            ],
        },
    },
    {
        'title': 'Contrôle des accès réseau',
        'description': 'Le réseau doit être segmenté et les accès contrôlés par politique.',
        'severity': 'HIGH',
        'evidence': {
            True: [
                "VLAN séparés pour R&D, production et visiteurs, firewall inter-VLAN configuré.",
                "NAC Cisco déployé, authentification 802.1X sur tous les ports réseau.",
                "Pentest réseau annuel réalisé, 0 vulnérabilité critique identifiée en 2026.",
                "Politique de filtrage réseau documentée, flux autorisés uniquement par whitelist.",
            ],
            False: [
                "Réseau R&D et réseau visiteurs sur le même VLAN sans segmentation.",
                "Ports réseau non utilisés actifs et accessibles en zone commune.",
                "Aucune authentification réseau, tout appareil peut se connecter au LAN.",
                "Pentest non réalisé depuis 2023, vulnérabilités potentielles non identifiées.",
            ],
        },
    },
    {
        'title': 'Classification et traitement des données',
        'description': 'Les données doivent être classifiées selon leur sensibilité et traitées en conséquence.',
        'severity': 'HIGH',
        'evidence': {
            True: [
                "Politique de classification TISAX implémentée, 4 niveaux définis et appliqués.",
                "Formation classification dispensée à tous les ingénieurs R&D en janvier 2026.",
                "Outils DLP configurés pour détecter les transferts de données non classifiées.",
                "Inventaire des données prototypes mis à jour trimestriellement, responsable identifié.",
            ],
            False: [
                "Aucune politique de classification des données en vigueur.",
                "Données prototype OEM partagées sans vérification du niveau d'accréditation TISAX.",
                "Formation classification non dispensée, employés ignorent les niveaux de sensibilité.",
                "DLP non déployé, transferts non contrôlés vers des supports externes.",
            ],
        },
    },
]


REVIEWER_COMMENTS_OK = [
    "Contrôle conforme aux exigences, documentation complète et à jour.",
    "Validation satisfaisante, preuves suffisantes fournies lors de l'audit.",
    "Conformité vérifiée, mesures correctives antérieures bien implémentées.",
    "Evidence solide, le contrôle est opérationnel et testé régulièrement.",
]
REVIEWER_COMMENTS_NOK = [
    "Non-conformité majeure identifiée, action corrective immédiate requise.",
    "Documentation insuffisante, absence de preuve d'implémentation effective.",
    "Contrôle non opérationnel, risque élevé pour la sécurité du système.",
    "Mesures préventives manquantes, revue complète nécessaire avant prochaine audit.",
]
RECOMMENDATIONS_OK = [
    "Maintenir le niveau actuel, planifier la prochaine revue",
    "Documenter les améliorations continues",
    "Conserver dans le dossier de conformité",
]
RECOMMENDATIONS_NOK = [
    "Implémenter immédiatement les contrôles manquants",
    "Former l'équipe et mettre en place les procédures",
    "Revoir la politique de sécurité et effectuer un audit de suivi",
    "Escalader à la Direction pour allocation de ressources",
]


NORM_CONFIG = {
    'ISO27001': {
        'rules': ISO27001_RULES,
        'description': 'ISO/IEC 27001 — Système de management de la sécurité de l\'information',
        'min_samples': 300,
    },
    'TISAX': {
        'rules': TISAX_RULES,
        'description': 'TISAX — Trusted Information Security Assessment Exchange (automotive)',
        'min_samples': 300,
    },
}


def _get_or_create_norm_with_rules(name, description, rule_defs):
    """Get or create a norm and ensure it has all rules defined."""
    from api.models import Rule as RuleModel
    norm, _ = Norme.objects.get_or_create(
        name__iexact=name,
        defaults={'name': name, 'description': description},
    )
    # Handle case where get_or_create didn't match iexact
    existing = Norme.objects.filter(name__iexact=name).first()
    if existing:
        norm = existing

    existing_rules = {r.title: r for r in norm.rules.all()}
    rules = []
    for rdef in rule_defs:
        rule = existing_rules.get(rdef['title'])
        if rule is None:
            rule = RuleModel.objects.create(
                norme=norm,
                title=rdef['title'],
                description=rdef['description'],
                severity=rdef['severity'],
            )
        rules.append(rule)
    return norm, rules


class Command(BaseCommand):
    help = 'Generate realistic synthetic training data for ISO 27001 and TISAX norms.'

    def add_arguments(self, parser):
        parser.add_argument('--norm', type=str, default='all',
                            help='Norm to generate: ISO27001 | TISAX | all (default: all)')
        parser.add_argument('--samples', type=int, default=0,
                            help='Total samples to generate (0 = use minimum per norm)')
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, **options):
        random.seed(options['seed'])
        target_norm = options['norm'].upper()
        extra_samples = options['samples']

        norms_to_process = (
            list(NORM_CONFIG.keys())
            if target_norm == 'ALL'
            else [target_norm] if target_norm in NORM_CONFIG
            else None
        )
        if norms_to_process is None:
            self.stderr.write(f"Unknown norm: {target_norm}. Choose: ISO27001, TISAX, all")
            return

        for norm_name in norms_to_process:
            cfg = NORM_CONFIG[norm_name]
            target = extra_samples if extra_samples > 0 else cfg['min_samples']
            self._generate_for_norm(norm_name, cfg, target)

    def _generate_for_norm(self, norm_name, cfg, target_samples):
        self.stdout.write(f'\n[{norm_name}] Generating {target_samples} samples...')

        norm, rules = _get_or_create_norm_with_rules(
            norm_name, cfg['description'], cfg['rules']
        )

        existing = RuleTrainingSample.objects.filter(norm=norm).count()
        needed = max(0, target_samples - existing)

        if needed == 0:
            self.stdout.write(f'  Already has {existing} samples — skipping.')
            return

        self.stdout.write(f'  Existing: {existing}, need to create: {needed}')

        # Target ~55% approved, 45% rejected for realistic distribution
        approved_target = int(round(needed * 0.55))
        rejected_target = needed - approved_target

        created = 0
        with transaction.atomic():
            for i in range(needed):
                is_approved = i < approved_target
                label = 'approved' if is_approved else 'rejected'

                # Pick a random rule
                rule_def = random.choice(cfg['rules'])
                rule = next((r for r in rules if r.title == rule_def['title']), rules[0])

                evidence_text = random.choice(rule_def['evidence'][is_approved])
                reviewer_comment = random.choice(
                    REVIEWER_COMMENTS_OK if is_approved else REVIEWER_COMMENTS_NOK
                )
                recommendation = random.choice(
                    RECOMMENDATIONS_OK if is_approved else RECOMMENDATIONS_NOK
                )

                # Avoid exact duplicates
                if RuleTrainingSample.objects.filter(
                    norm=norm, rule=rule, evidence_text=evidence_text, label=label
                ).exists():
                    # Add variation
                    evidence_text = evidence_text + f" (ref. audit {random.randint(1000, 9999)}/{2026})"

                RuleTrainingSample.objects.create(
                    norm=norm,
                    rule=rule,
                    rule_title=rule.title,
                    rule_description=rule.description,
                    evidence_text=evidence_text,
                    reviewer_comment=reviewer_comment,
                    recommendation=recommendation,
                    label=label,
                    final_document_decision=label,
                    confidence_score=round(random.uniform(0.70, 0.97) if is_approved else random.uniform(0.55, 0.90), 2),
                    semantic_score=round(random.uniform(0.65, 0.95) if is_approved else random.uniform(0.50, 0.85), 2),
                )
                created += 1

        final_total = RuleTrainingSample.objects.filter(norm=norm).count()
        approved_total = RuleTrainingSample.objects.filter(norm=norm, label='approved').count()
        rejected_total = RuleTrainingSample.objects.filter(norm=norm, label='rejected').count()
        rules_covered = RuleTrainingSample.objects.filter(norm=norm).values('rule_id').distinct().count()

        self.stdout.write(self.style.SUCCESS(
            f'  Created {created} samples. Total: {final_total} '
            f'(approved={approved_total}, rejected={rejected_total}, rules_covered={rules_covered}/{len(rules)})'
        ))
