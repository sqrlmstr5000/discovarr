import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator
# Import necessary models and the database proxy
from services.models import Media, WatchHistory, database

def upgrade(migrator: SchemaMigrator):
    # === Media table changes ===
    # Define the new column with null=True initially
    source_provider = CharField(null=True)

    run_migrations(
        migrator.add_column('media', 'source_provider', source_provider),
    )

def rollback(migrator: SchemaMigrator):
    # === Media table rollback ===
    # To properly rollback, first allow NULLs again, then drop the column
    run_migrations(
        migrator.drop_column('media', 'source_provider'),
    )

