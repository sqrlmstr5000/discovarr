import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    media_id = CharField(null=True)

    run_migrations(
        migrator.add_column('watchhistory', 'media_id', media_id),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('watchhistory', 'media_id'),
    )

