import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator
# Import necessary models and the database proxy
from services.models import Media, WatchHistory, database

def upgrade(migrator: SchemaMigrator):
    # === Media table changes ===
    # Define the new column with null=True initially
    processed = BooleanField(default=False)
    processed_at = DateTimeField(null=True)

    run_migrations(
        migrator.add_column('watchhistory', 'processed', processed),
        migrator.add_column('watchhistory', 'processed_at', processed_at),
    )

def rollback(migrator: SchemaMigrator):
    # === Media table rollback ===
    # To properly rollback, first allow NULLs again, then drop the column
    run_migrations(
        migrator.drop_column('watchhistory', 'processed'),
        migrator.drop_column('watchhistory', 'processed_at'),
    )

