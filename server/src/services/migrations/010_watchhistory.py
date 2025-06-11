import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    poster_url = CharField(null=True)

    run_migrations(
        migrator.add_column('watchhistory', 'poster_url', poster_url),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('watchhistory', 'poster_url'),
    )

