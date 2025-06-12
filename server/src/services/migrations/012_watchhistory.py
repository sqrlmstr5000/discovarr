import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    source = CharField(null=True)

    run_migrations(
        migrator.add_column('watchhistory', 'source', source),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('watchhistory', 'source'),
    )

