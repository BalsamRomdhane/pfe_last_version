# Migration 0014 — log_output sur TrainingJob
#
# HISTORIQUE DU PROBLEME :
#   La colonne log_output a ete ajoutee physiquement dans PostgreSQL
#   via une ancienne branche de migrations (0011_trainingjob_mlopsconfig
#   de l'ancienne branche, qui n'existe plus sur disque mais reste dans
#   django_migrations). La colonne est donc deja presente dans la table
#   api_trainingjob mais cette migration (0014) n'est pas marquee comme
#   appliquee dans django_migrations.
#
# SOLUTION — SeparateDatabaseAndState :
#   - database_operations = [] : ne pas executer de DDL (la colonne existe deja)
#   - state_operations = [AddField] : mettre a jour l'etat Django uniquement
#
# Resultat : idempotent sur base existante ET correct sur base neuve.
#   - Base existante : AddField saute la partie SQL, enregistre juste l'etat
#   - Base neuve    : SeparateDatabaseAndState avec state_operations cree
#                     le champ dans l'etat Django ; la table est creee par
#                     0011_mlopsconfig_trainingjob SANS log_output, donc
#                     on a besoin d'un AddField reel pour les nouvelles bases.
#
# IMPORTANT : Pour distinguer les deux cas (base existante vs neuve),
#   on utilise migrations.RunSQL avec IF NOT EXISTS — compatible PostgreSQL.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_rename_api_document_standard_4f81a0_idx_api_documen_standar_63ca70_idx_and_more'),
    ]

    operations = [
        # RunSQL avec IF NOT EXISTS : idempotent sur toutes les bases
        # - Base existante (log_output deja la) : ADD COLUMN est ignoree silencieusement
        # - Base neuve (log_output absente)      : ADD COLUMN est executee normalement
        migrations.RunSQL(
            sql="""
                ALTER TABLE api_trainingjob
                ADD COLUMN IF NOT EXISTS log_output text NOT NULL DEFAULT '';
            """,
            reverse_sql="""
                ALTER TABLE api_trainingjob
                DROP COLUMN IF EXISTS log_output;
            """,
            # state_operations : dit a Django que le champ existe dans le modele
            state_operations=[
                migrations.AddField(
                    model_name='trainingjob',
                    name='log_output',
                    field=models.TextField(blank=True, default=''),
                ),
            ],
        ),
    ]
