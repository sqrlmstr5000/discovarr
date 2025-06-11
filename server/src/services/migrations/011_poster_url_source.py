import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    poster_url_source = CharField(null=True)

    run_migrations(
        migrator.add_column('media', 'poster_url_source', poster_url_source),
        migrator.add_column('watchhistory', 'poster_url_source', poster_url_source),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('media', 'poster_url_source'),
        migrator.drop_column('watchhistory', 'poster_url_source'),
    )

