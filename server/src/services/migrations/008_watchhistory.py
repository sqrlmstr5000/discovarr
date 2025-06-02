import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    processed = BooleanField(default=False)
    processed_at = DateTimeField(null=True)

    run_migrations(
        migrator.add_column('watchhistory', 'processed', processed),
        migrator.add_column('watchhistory', 'processed_at', processed_at),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('watchhistory', 'processed'),
        migrator.drop_column('watchhistory', 'processed_at'),
    )

