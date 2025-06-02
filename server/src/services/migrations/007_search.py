import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    last_run_date = DateTimeField(null=True)

    run_migrations(
        migrator.add_column('search', 'last_run_date', last_run_date),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('search', 'last_run_date'),
    )

