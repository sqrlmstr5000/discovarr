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
    genre = pw.TextField(null=True)

    run_migrations(
        migrator.add_column('media', 'genre', genre),
    )

def rollback(migrator: SchemaMigrator):
    """
    Reverts the migration by removing the added fields from the 'media' table.
    """
    run_migrations(
        migrator.drop_column('media', 'genre'),
    )

