"""
generate_diverse_datasets — Génère des datasets avec vocabulaire partagé
entre classes conforme/non-conforme pour éviter la séparabilité triviale.

Stratégie : chaque thème (ex: gestion des accès) a des variantes conformes
ET non-conformes qui partagent le même vocabulaire de base.
La différence est dans les preuves concrètes (dates, versions, résultats).

Usage:
    python manage.py generate_diverse_datasets
    python manage.py generate_diverse_datasets --norm ISO27001 --count 500
"""
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import (
    Norme, Rule, Document, Validation,
    TrainingSample, RuleTrainingSample,
)

# ── Template engine — same theme, different compliance evidence ──────────────

THEMES_ISO27001 = {
    'gestion_acces': {
        'context': [
            "Le système de gestion des accès de l'organisation couvre l'ensemble des applications critiques.",
            "La politique IAM (Identity and Access Management) encadre les droits des utilisateurs.",
            "Le contrôle des accès aux ressources sensibles fait l'objet d'une procédure dédiée.",
            "L'attribution des droits d'accès suit le principe du moindre privilège.",
            "La gestion des comptes utilisateurs implique les équipes RH, DSI et managers.",
        ],
        'evidence_ok': [
            "Une revue trimestrielle des droits a été réalisée le {date}, avec {n} comptes révoqués.",
            "L'authentification multi-facteurs est déployée sur {pct}% des comptes, validée par audit du {date}.",
            "Le processus de révocation est documenté (procédure IAM-{ref}) et testé le {date}.",
            "Les comptes privilégiés sont gérés via PAM depuis le {date}, couvrant {n} administrateurs.",
            "La matrice des droits d'accès a été mise à jour le {date} et validée par le RSSI.",
        ],
        'evidence_nok': [
            "Une revue des droits a été initiée mais n'a pas encore été finalisée à ce jour.",
            "L'authentification multi-facteurs est en cours de déploiement sur quelques systèmes.",
            "Le processus de révocation existe dans les pratiques mais n'est pas encore formalisé.",
            "Les comptes privilégiés sont recensés mais ne font pas l'objet d'une supervision dédiée.",
            "La matrice des droits est disponible mais sa mise à jour n'est pas planifiée régulièrement.",
        ],
    },
    'gestion_incidents': {
        'context': [
            "Le processus de gestion des incidents de sécurité structure la réponse de l'équipe IT.",
            "La détection et le traitement des incidents s'appuie sur les outils de surveillance déployés.",
            "Un dispositif de réponse aux incidents est en place pour gérer les événements de sécurité.",
            "La procédure d'escalade des incidents définit les niveaux de criticité et les délais.",
            "L'équipe sécurité est responsable du traitement et de la documentation des incidents.",
        ],
        'evidence_ok': [
            "Le MTTD moyen est de {n}h sur Q{q} {year}, mesuré via le SIEM et documenté dans le rapport mensuel.",
            "{n} incidents traités en {year}, tous documentés avec PV de clôture signé par le RSSI.",
            "Un exercice de simulation d'incident a été réalisé le {date}, résultat : RTO de {n}h atteint.",
            "La procédure PROC-INC-{ref} est en vigueur depuis le {date}, testée et validée par le comité.",
            "Le SOC assure une surveillance 24/7 avec une alerte traitée en moins de {n}min en moyenne.",
        ],
        'evidence_nok': [
            "Le délai moyen de détection n'est pas encore mesuré faute d'outil de reporting.",
            "Les incidents sont traités mais leur documentation n'est pas systématiquement archivée.",
            "Aucun exercice de simulation n'a été organisé cette année en raison de contraintes calendaires.",
            "La procédure existe mais n'a pas été révisée depuis plus d'un an et peut être obsolète.",
            "La surveillance est assurée en heures ouvrables uniquement, sans couverture nocturne.",
        ],
    },
    'sauvegarde': {
        'context': [
            "La politique de sauvegarde des données critiques est un élément central de la continuité.",
            "Les sauvegardes couvrent les serveurs de production, les bases de données et les fichiers partagés.",
            "Le plan de reprise après incident dépend de la disponibilité et de l'intégrité des sauvegardes.",
            "Le RTO et le RPO définis par la Direction encadrent les exigences de sauvegarde.",
            "L'infrastructure de sauvegarde est maintenue par l'équipe infrastructure sous supervision DSI.",
        ],
        'evidence_ok': [
            "Les sauvegardes quotidiennes sont chiffrées AES-{bits} et testées mensuellement, dernier test le {date}.",
            "Le RPO de {n}h et le RTO de {m}h ont été validés lors du test de reprise du {date}.",
            "Un site DR distant de {km}km héberge les répliques synchrones depuis le {date}.",
            "Le rapport de sauvegarde du {date} confirme {pct}% de succès sur les {n} derniers jours.",
            "Les clés de chiffrement des backups sont gérées via Vault, rotation effectuée le {date}.",
        ],
        'evidence_nok': [
            "Les sauvegardes sont effectuées régulièrement mais leur chiffrement n'est pas encore activé.",
            "Le RPO et le RTO sont définis mais n'ont pas été testés en conditions réelles récemment.",
            "Le site de sauvegarde est sur le même bâtiment que la production, sans site distant.",
            "Les rapports de sauvegarde sont générés mais ne font pas l'objet d'une revue systématique.",
            "La gestion des clés de chiffrement n'est pas formalisée dans une procédure documentée.",
        ],
    },
    'chiffrement': {
        'context': [
            "La politique de chiffrement définit les standards applicables aux données de l'organisation.",
            "Le chiffrement protège les données en transit et au repos conformément aux exigences ISO.",
            "Les algorithmes et protocoles de chiffrement utilisés font l'objet d'une politique documentée.",
            "La gestion des clés cryptographiques est un composant essentiel de la sécurité des données.",
            "Les certificats TLS et les clés de chiffrement sont supervisés par l'équipe sécurité.",
        ],
        'evidence_ok': [
            "TLS {ver} est enforced sur {pct}% des services, validé par scan du {date}.",
            "Les bases de données critiques sont chiffrées via TDE depuis le {date}, couverture {pct}%.",
            "La rotation des clés est planifiée annuellement, dernière rotation effectuée le {date}.",
            "L'inventaire des certificats est à jour au {date}, {n} certificats gérés via automation.",
            "Les algorithmes obsolètes (RC4, DES, MD5) ont été désactivés suite à l'audit du {date}.",
        ],
        'evidence_nok': [
            "TLS est déployé sur la majorité des services mais quelques applications legacy restent en HTTP.",
            "Le chiffrement des bases de données est planifié mais pas encore implémenté sur tous les serveurs.",
            "La politique de rotation des clés est définie mais son application n'est pas tracée.",
            "Certains certificats ont expiré récemment sans que le renouvellement soit automatisé.",
            "Des algorithmes de chiffrement vieillissants subsistent sur des systèmes en cours de migration.",
        ],
    },
    'journalisation': {
        'context': [
            "La journalisation des événements de sécurité permet la détection et l'investigation d'incidents.",
            "Les journaux système alimentent le SIEM pour la surveillance temps réel de l'infrastructure.",
            "La politique de rétention des logs respecte les exigences légales et contractuelles.",
            "La centralisation des journaux garantit leur disponibilité pour les audits de sécurité.",
            "L'analyse des journaux est réalisée par le SOC selon un processus documenté.",
        ],
        'evidence_ok': [
            "Le SIEM centralise les logs de {n} sources, rétention {m} mois, dernier audit le {date}.",
            "Les logs sont stockés en lecture seule sur support WORM depuis le {date}, hash SHA-256 validé.",
            "Le SOC analyse {n} alertes par semaine, délai moyen de traitement : {m}h, rapport du {date}.",
            "La rétention de {m} mois est conforme à la LPM, vérifiée lors de l'audit du {date}.",
            "Des alertes sont configurées pour {n} patterns d'attaque, testées le {date}.",
        ],
        'evidence_nok': [
            "La centralisation des logs est partielle, certains serveurs envoient encore localement.",
            "La rétention des logs varie selon les serveurs et n'est pas standardisée à {m} mois.",
            "Le SOC analyse les alertes en journée mais la couverture nocturne n'est pas assurée.",
            "Les logs sont conservés mais leur intégrité n'est pas vérifiée automatiquement.",
            "Les alertes SIEM sont configurées mais n'ont pas été révisées depuis plusieurs mois.",
        ],
    },
    'fournisseurs': {
        'context': [
            "La gestion des fournisseurs IT encadre les relations avec les prestataires et sous-traitants.",
            "Les partenaires ayant accès aux systèmes ou données font l'objet d'une évaluation sécurité.",
            "Les contrats fournisseurs incluent des clauses sécurité et de confidentialité.",
            "Le registre des fournisseurs liste les prestataires actifs et leur niveau d'accréditation.",
            "Les accès accordés aux tiers sont tracés et révoqués à la fin des missions.",
        ],
        'evidence_ok': [
            "{n} fournisseurs évalués en {year}, questionnaire sécurité complété, rapport archivé au {date}.",
            "Les clauses RGPD et ISO 27001 sont intégrées dans {pct}% des contrats depuis le {date}.",
            "Le registre des fournisseurs est à jour au {date}, {n} prestataires actifs, {m} critiques.",
            "Les accès tiers ont été audités le {date} : {n} comptes révoqués suite à fin de mission.",
            "L'audit annuel des fournisseurs critiques a été réalisé le {date}, {n}/{m} conformes.",
        ],
        'evidence_nok': [
            "L'évaluation sécurité des fournisseurs est réalisée ponctuellement sans processus formalisé.",
            "Les clauses sécurité sont incluses dans la majorité des contrats mais sans template standard.",
            "Le registre des fournisseurs existe mais sa mise à jour n'est pas effectuée régulièrement.",
            "Les accès tiers sont révoqués à la fin des missions mais sans procédure automatisée.",
            "L'audit des fournisseurs critiques est prévu mais n'a pas encore été réalisé cette année.",
        ],
    },
    'continuite': {
        'context': [
            "Le plan de continuité d'activité (PCA) garantit la reprise des services essentiels après sinistre.",
            "La continuité opérationnelle s'appuie sur une analyse d'impact et des procédures de reprise.",
            "Le PCA est élaboré en collaboration avec les métiers et validé par la Direction.",
            "Des exercices réguliers testent la robustesse des procédures de continuité.",
            "Le BIA identifie les processus critiques et les délais de reprise acceptables.",
        ],
        'evidence_ok': [
            "Le PCA a été approuvé par le COMEX le {date} et testé avec succès le {date2}.",
            "Le BIA de {year} identifie {n} processus critiques avec RTO de {m}h, documenté au {date}.",
            "Un exercice de reprise a été organisé le {date}, RTO de {m}h atteint, PV disponible.",
            "Le site de repli est opérationnel depuis le {date}, basculement testé en {m}min.",
            "La formation continuité a été dispensée à {n} collaborateurs clés le {date}.",
        ],
        'evidence_nok': [
            "Le PCA est documenté mais n'a pas été testé depuis plus de {m} mois.",
            "Le BIA a été réalisé mais les processus critiques n'ont pas encore de RTO défini.",
            "Les exercices de reprise sont planifiés mais ont été reportés pour raisons opérationnelles.",
            "Le site de repli est identifié mais son opérationnalité n'a pas été vérifiée récemment.",
            "La formation continuité est prévue au plan de formation mais pas encore dispensée.",
        ],
    },
    'risques': {
        'context': [
            "La gestion des risques de sécurité est un processus continu documenté dans le SMSI.",
            "L'analyse de risques couvre l'ensemble du périmètre défini dans la déclaration d'applicabilité.",
            "Les risques identifiés sont évalués selon une matrice probabilité/impact validée.",
            "Le registre des risques est mis à jour régulièrement et présenté au comité de direction.",
            "Les traitements de risques (réduction, transfert, acceptation) sont décidés par la Direction.",
        ],
        'evidence_ok': [
            "L'analyse de risques {year} a identifié {n} risques, {m} traités, registre mis à jour au {date}.",
            "La déclaration d'applicabilité version {ref} a été approuvée le {date} par le RSSI et DG.",
            "Le registre des risques est présenté trimestriellement au COMEX, dernière présentation {date}.",
            "Les {n} risques résiduels acceptés ont été validés par la Direction le {date}.",
            "L'analyse de risques couvre {pct}% du périmètre ISO 27001, attestée par auditeur externe.",
        ],
        'evidence_nok': [
            "L'analyse de risques a été réalisée mais n'est pas mise à jour au rythme prévu.",
            "La déclaration d'applicabilité existe mais sa révision annuelle n'est pas effectuée.",
            "Le registre des risques est tenu mais sa présentation au COMEX n'est pas régulière.",
            "Certains risques acceptés ne font pas l'objet d'une validation formelle de la Direction.",
            "La couverture de l'analyse de risques est partielle, certains domaines non encore évalués.",
        ],
    },
}

THEMES_TISAX = {
    'protection_prototypes': {
        'context': [
            "La protection des informations de prototype est essentielle dans le secteur automobile.",
            "Les données de développement véhicule sont classifiées et protégées selon le niveau TISAX.",
            "Le plan de protection des prototypes définit les mesures physiques et numériques applicables.",
            "L'accès aux informations de prototype est contrôlé et tracé conformément à l'accréditation TISAX.",
            "Les fichiers de conception automobile font l'objet d'une politique de classification stricte.",
        ],
        'evidence_ok': [
            "La classification des données prototypes est appliquée sur {pct}% des actifs, auditée le {date}.",
            "Le watermark numérique est actif sur tous les fichiers CAO depuis le {date}.",
            "L'accès aux fichiers prototypes requiert double authentification depuis le {date}.",
            "Le PPP v{ref} a été approuvé par le Directeur R&D et le RSSI le {date}.",
            "L'audit TISAX AL{n} a été obtenu le {date}, prochaine échéance {date2}.",
        ],
        'evidence_nok': [
            "La classification des informations prototype est définie mais son application est partielle.",
            "Le marquage des fichiers CAO est pratiqué sur les projets récents mais pas sur l'historique.",
            "L'authentification renforcée est déployée sur les systèmes principaux, en cours pour les autres.",
            "Le plan de protection des prototypes est en cours de révision pour la prochaine version.",
            "La certification TISAX est en préparation et n'a pas encore été obtenue.",
        ],
    },
    'visiteurs': {
        'context': [
            "La procédure de gestion des visiteurs encadre les accès aux zones sensibles du site.",
            "Les visiteurs en zone technique font l'objet d'une escorte et d'un enregistrement.",
            "L'accord de confidentialité est requis pour tout accès aux zones de développement prototype.",
            "Le registre des visites permet la traçabilité des personnes ayant accédé au site.",
            "Les badges visiteurs temporaires sont attribués et révoqués de façon contrôlée.",
        ],
        'evidence_ok': [
            "{n} visites enregistrées en {year}, 0 anomalie détectée, registre audité le {date}.",
            "100% des visiteurs zone R&D ont signé un NDA spécifique depuis le {date}.",
            "Les badges visiteurs sont révoqués automatiquement après {m}h, implémenté le {date}.",
            "La procédure d'escorte a été formalisée (PROC-VIS-{ref}) et appliquée depuis le {date}.",
            "La formation escorte a été dispensée à {n} agents d'accueil le {date}.",
        ],
        'evidence_nok': [
            "L'enregistrement des visites est effectué mais de façon manuelle sans traçabilité électronique.",
            "La signature du NDA est pratiquée pour les projets sensibles mais pas systématiquement.",
            "Les badges visiteurs ont une validité fixe mais leur révocation n'est pas automatisée.",
            "La procédure d'escorte est connue des équipes mais pas encore formellement documentée.",
            "La formation escorte est planifiée mais n'a pas encore été dispensée cette année.",
        ],
    },
    'securite_physique': {
        'context': [
            "La sécurité physique du site protège les actifs matériels et informationnels de l'organisation.",
            "Le contrôle d'accès physique structure les niveaux de sécurité des différentes zones.",
            "La vidéosurveillance et les systèmes anti-intrusion contribuent à la sécurité périmétrique.",
            "La politique clean desk réduit le risque d'exposition des informations confidentielles.",
            "Les armoires sécurisées et les broyeurs protègent les supports physiques sensibles.",
        ],
        'evidence_ok': [
            "Le contrôle biométrique zone R&D est opérationnel depuis le {date}, {n} accès/jour tracés.",
            "La vidéosurveillance couvre {pct}% des zones sensibles, rétention {m} jours, validée au {date}.",
            "L'audit clean desk du {date} montre un taux de conformité de {pct}%.",
            "Les {n} armoires sécurisées grade {g} sont inventoriées et testées le {date}.",
            "Le dernier rapport de sécurité physique du {date} conclut à {pct}% de conformité.",
        ],
        'evidence_nok': [
            "Le contrôle biométrique est déployé sur les zones principales, en cours d'extension.",
            "La vidéosurveillance couvre les zones d'accès principaux mais pas l'ensemble des zones sensibles.",
            "L'audit clean desk est réalisé ponctuellement sans fréquence définie dans la politique.",
            "Les armoires sécurisées sont disponibles mais leur utilisation n'est pas systématique.",
            "Le rapport de sécurité physique est en retard, l'audit n'ayant pas été planifié cette année.",
        ],
    },
    'acces_reseau': {
        'context': [
            "La segmentation réseau isole les zones sensibles du reste de l'infrastructure.",
            "Le contrôle des accès réseau empêche les connexions non autorisées aux ressources protégées.",
            "La politique de filtrage réseau définit les flux autorisés entre les différents segments.",
            "L'authentification réseau garantit l'identité des équipements se connectant au LAN.",
            "La surveillance du trafic réseau permet de détecter les comportements anormaux.",
        ],
        'evidence_ok': [
            "La segmentation VLAN est en place depuis le {date}, {n} VLAN définis, auditée le {date2}.",
            "L'authentification 802.1X couvre {pct}% des ports réseau depuis le {date}.",
            "Le pare-feu NG avec inspection SSL est opérationnel depuis le {date}, règles révisées au {date2}.",
            "Le DLP bloque les transferts non autorisés depuis le {date}, {n} incidents bloqués en {year}.",
            "Le pentest réseau du {date} n'a identifié aucune vulnérabilité critique.",
        ],
        'evidence_nok': [
            "La segmentation réseau est en cours de déploiement, partiellement implémentée à ce jour.",
            "L'authentification 802.1X est déployée sur les switchs principaux, en cours pour les autres.",
            "Le pare-feu périmétrique est opérationnel mais ses règles n'ont pas été révisées récemment.",
            "Le DLP est en phase pilote sur quelques postes, le déploiement complet n'est pas finalisé.",
            "Le dernier pentest date de plus d'un an, le prochain n'est pas encore planifié.",
        ],
    },
    'confidentialite': {
        'context': [
            "La protection de la confidentialité des informations est un engagement contractuel avec les OEM.",
            "La classification des informations permet d'appliquer des mesures de protection adaptées.",
            "Les accords de confidentialité (NDA) encadrent les échanges avec les partenaires automobiles.",
            "La politique de confidentialité définit les obligations des collaborateurs et sous-traitants.",
            "La prévention des fuites de données (DLP) protège les informations classifiées.",
        ],
        'evidence_ok': [
            "{n} NDA actifs avec les partenaires OEM, tous à jour au {date}.",
            "La formation confidentialité a été suivie par {pct}% des ingénieurs le {date}.",
            "Le DLP a détecté et bloqué {n} tentatives d'exfiltration en {year}, rapport disponible.",
            "La classification des actifs a été réalisée pour {pct}% du périmètre au {date}.",
            "L'audit confidentialité {year} a validé la conformité TISAX AL{n} le {date}.",
        ],
        'evidence_nok': [
            "Les NDA avec les partenaires sont en place mais leur renouvellement n'est pas systématique.",
            "La formation confidentialité est dispensée à l'onboarding mais sans rappel annuel formalisé.",
            "Le DLP est configuré mais ses alertes ne font pas l'objet d'une revue régulière.",
            "La classification des actifs est partielle, certains domaines n'ayant pas encore été traités.",
            "La conformité TISAX est en cours d'évaluation, la certification n'ayant pas encore été obtenue.",
        ],
    },
}


# ── Template filler — injects realistic values ───────────────────────────────

DATES = [
    "02/01/2026", "15/01/2026", "28/01/2026", "10/02/2026", "22/02/2026",
    "05/03/2026", "18/03/2026", "01/04/2026", "14/04/2026", "28/04/2026",
    "12/05/2026", "26/05/2026", "03/06/2026", "17/06/2026", "30/06/2026",
]

def fill_template(template: str) -> str:
    import random
    replacements = {
        '{date}':  random.choice(DATES),
        '{date2}': random.choice(DATES),
        '{n}':     str(random.randint(3, 150)),
        '{m}':     str(random.randint(2, 24)),
        '{pct}':   str(random.randint(75, 100)),
        '{ref}':   f"{random.randint(100,999)}-{random.randint(10,99)}",
        '{bits}':  random.choice(['128', '192', '256']),
        '{km}':    str(random.randint(30, 200)),
        '{ver}':   random.choice(['1.2', '1.3']),
        '{year}':  random.choice(['2025', '2026']),
        '{q}':     str(random.randint(1, 4)),
        '{g}':     random.choice(['2', '3', '4']),
    }
    result = template
    for key, val in replacements.items():
        result = result.replace(key, val)
    return result


def build_document_text(theme_data: dict, is_approved: bool) -> str:
    """Build a realistic document text mixing context + evidence."""
    import random
    context_lines = random.sample(theme_data['context'], min(3, len(theme_data['context'])))
    evidence_pool = theme_data['evidence_ok'] if is_approved else theme_data['evidence_nok']
    evidence_lines = random.sample(evidence_pool, min(3, len(evidence_pool)))

    paragraphs = []
    paragraphs.append("RAPPORT D'ÉVALUATION DE CONFORMITÉ\n")
    for ctx in context_lines:
        paragraphs.append(fill_template(ctx))
    paragraphs.append("\nÉLÉMENTS DE PREUVE :")
    for ev in evidence_lines:
        paragraphs.append("• " + fill_template(ev))
    if is_approved:
        conclusions = [
            f"CONCLUSION : Le contrôle est jugé conforme suite à la revue du {random.choice(DATES)}.",
            f"VERDICT : Satisfaisant. Les preuves collectées démontrent l'implémentation effective.",
            f"RÉSULTAT : La conformité est attestée pour la période {random.choice(['Q1','Q2','Q3','Q4'])} 2026.",
        ]
    else:
        conclusions = [
            f"CONCLUSION : Des lacunes ont été identifiées lors de la revue du {random.choice(DATES)}.",
            f"VERDICT : Insuffisant. Les preuves ne démontrent pas une implémentation complète et testée.",
            f"RÉSULTAT : Des actions correctives sont requises avant la prochaine échéance d'audit.",
        ]
    paragraphs.append("\n" + random.choice(conclusions))
    return "\n".join(paragraphs)


NORM_THEMES = {
    'ISO27001': THEMES_ISO27001,
    'TISAX':    THEMES_TISAX,
}

NORM_KEY_MAP = [
    ('9001', 'ISO9001'),
    ('27001', 'ISO27001'),
    ('tisax', 'TISAX'),
]

def _norm_key(name: str) -> str:
    n = name.lower().replace(' ', '').replace('-', '')
    for frag, key in NORM_KEY_MAP:
        if frag in n:
            return key
    return None

REVIEWER_OK = [
    "Conforme aux exigences. Les preuves d'implémentation sont disponibles et vérifiées.",
    "Validation satisfaisante. La politique est appliquée et documentée.",
    "Approuvé. Le contrôle est opérationnel et les indicateurs sont atteints.",
]
REVIEWER_NOK = [
    "Non-conformité identifiée. Les preuves d'implémentation sont insuffisantes.",
    "Insuffisant. La politique existe mais son application effective n'est pas démontrée.",
    "Rejeté. Des actions correctives sont requises pour atteindre la conformité.",
]


class Command(BaseCommand):
    help = 'Generate diverse realistic datasets with shared vocabulary between classes.'

    def add_arguments(self, parser):
        parser.add_argument('--norm', type=str, default='all')
        parser.add_argument('--count', type=int, default=500)
        parser.add_argument('--seed', type=int, default=2027)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        random.seed(options['seed'])
        dry = options['dry_run']
        target = options['norm'].upper()
        count = options['count']

        self.stdout.write(self.style.SUCCESS('=== GENERATE DIVERSE DATASETS ===\n'))

        for norm in Norme.objects.all():
            key = _norm_key(norm.name)
            if target != 'ALL' and key != target:
                continue
            if key not in NORM_THEMES:
                self.stdout.write(f'  [{norm.name}] No themes defined — skipping\n')
                continue

            themes = NORM_THEMES[key]
            theme_names = list(themes.keys())
            half = count // 2
            self.stdout.write(f'  [{norm.name}] Generating {half} approved + {half} rejected '
                              f'across {len(theme_names)} themes...')

            if dry:
                self.stdout.write(f'    DRY RUN — would create {count} training records\n')
                continue

            created = self._generate(norm, themes, theme_names, half)
            self.stdout.write(self.style.SUCCESS(f'    Created {created} records\n'))

        self.stdout.write('=== DONE ===')

    def _generate(self, norm, themes, theme_names, half_count):
        from django.db.models.signals import post_save
        from api import signals as api_sigs

        rules = list(norm.rules.order_by('id'))
        n_rules = len(rules)
        created = 0

        post_save.disconnect(api_sigs.create_training_sample_on_validation, sender=Validation)
        try:
            with transaction.atomic():
                for idx in range(half_count * 2):
                    is_approved = idx < half_count
                    label = 'approved' if is_approved else 'rejected'
                    # Cycle through themes to ensure even coverage
                    theme_name = theme_names[idx % len(theme_names)]
                    theme_data = themes[theme_name]

                    doc_text = build_document_text(theme_data, is_approved)

                    # Rule compliance: overlapping ranges for harder classification
                    # approved: 55-100%  rejected: 0-55%  (overlap at 55% zone)
                    if is_approved:
                        valid_count = random.randint(max(1, int(n_rules * 0.55)), n_rules)
                    else:
                        valid_count = random.randint(0, int(n_rules * 0.55))

                    shuffled = list(rules); random.shuffle(shuffled)
                    valid_ids = set(r.id for r in shuffled[:valid_count])

                    rule_results, features, fvec = {}, {}, []
                    appr_names, rejt_names = [], []
                    evidence_parts = []

                    for rule in rules:
                        is_valid = rule.id in valid_ids
                        rule_results[rule.title] = 1 if is_valid else 0
                        features[rule.title] = 1 if is_valid else 0
                        fvec.append(1 if is_valid else 0)
                        (appr_names if is_valid else rejt_names).append(rule.title)

                        # Evidence text = excerpt from shared document text
                        words = doc_text.split()
                        start = random.randint(0, max(0, len(words) - 20))
                        excerpt = ' '.join(words[start:start + random.randint(12, 25)])
                        if is_valid:
                            ev = f"[{rule.title}] Contrôle vérifié : {excerpt}"
                        else:
                            ev = f"[{rule.title}] Contrôle à renforcer : {excerpt}"
                        evidence_parts.append(ev)

                        doc = Document.objects.create(
                            file=f'diverse/{_norm_key(norm.name)}/{label}/{idx:04d}.pdf',
                            norme=norm,
                            employee_username=random.choice(['alice.martin','bob.dupont','claire.bernard','david.petit']),
                            employee_department=random.choice(['SECURITE','DSI','QUALITE']),
                            teamlead_username='teamlead_diverse',
                            status=label, final_decision=label,
                            decision_reason=random.choice(REVIEWER_OK if is_approved else REVIEWER_NOK),
                            reviewer_comment=random.choice(REVIEWER_OK if is_approved else REVIEWER_NOK),
                            approved_by='teamlead_diverse',
                            approved_at=timezone.now(), review_completed_at=timezone.now(),
                            is_finalized=True,
                        ) if rule == rules[0] else doc

                        Validation.objects.create(
                            document=doc, rule=rule,
                            teamlead_username='teamlead_diverse',
                            evidence_text=ev, is_valid=is_valid,
                        )
                        RuleTrainingSample.objects.create(
                            document=doc, norm=norm, rule=rule,
                            rule_title=rule.title, rule_description=rule.description or '',
                            evidence_text=ev, label='approved' if is_valid else 'rejected',
                            final_document_decision=label,
                            confidence_score=round(random.uniform(0.68, 0.95) if is_valid else random.uniform(0.50, 0.80), 2),
                            semantic_score=round(random.uniform(0.65, 0.92) if is_valid else random.uniform(0.48, 0.78), 2),
                        )

                    cs = round(valid_count / max(n_rules, 1) * 100, 1)
                    TrainingSample.objects.update_or_create(
                        document=doc,
                        defaults=dict(
                            norm_id=norm.id, features=features, feature_vector=fvec,
                            label=label, standard=norm.name,
                            teamlead_decision=label, final_decision=label,
                            approved=is_approved,
                            total_rules=n_rules, valid_rules_count=valid_count,
                            invalid_rules_count=n_rules - valid_count,
                            approved_rules=appr_names, rejected_rules=rejt_names,
                            rule_results_json=rule_results, compliance_score=cs,
                            confidence_score=round(cs / 100, 2),
                            document_text=doc_text[:3000],
                            evidence_text=' | '.join(evidence_parts),
                            rule_text=' | '.join(r.title for r in rules),
                        )
                    )
                    created += 1
        finally:
            post_save.connect(api_sigs.create_training_sample_on_validation, sender=Validation)
        return created
