import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):

    run_migrations(
        migrator.alter_column_type('settings', 'value', TextField(null=True))
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.alter_column_type('settings', 'value', CharField(null=True))
    )

