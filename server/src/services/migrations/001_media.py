"""
Migration 002: Add new fields to the Media table.

New fields:
- source_title
- similarity
- rt_url
- rt_score
- media_status
- release_date
- networks
- original_language
- ignore
"""
import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    """
    Applies the migration to add new fields to the 'media' table.
    """
    media_status_field = pw.CharField(null=True)
    release_date_field = pw.DateField(null=True)
    networks_field = pw.TextField(null=True)
    original_language_field = pw.CharField(null=True)

    run_migrations(
        migrator.add_column('media', 'media_status', media_status_field),
        migrator.add_column('media', 'release_date', release_date_field),
        migrator.add_column('media', 'networks', networks_field),
        migrator.add_column('media', 'original_language', original_language_field),
    )

def rollback(migrator: SchemaMigrator):
    """
    Reverts the migration by removing the added fields from the 'media' table.
    """
    run_migrations(
        migrator.drop_column('media', 'original_language'),
        migrator.drop_column('media', 'networks'),
        migrator.drop_column('media', 'release_date'),
        migrator.drop_column('media', 'media_status'),
    )

