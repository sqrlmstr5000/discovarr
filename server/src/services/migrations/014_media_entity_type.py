import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator
# Import necessary models and the database proxy
from services.models import Media, WatchHistory, database

def upgrade(migrator: SchemaMigrator):
    # === Media table changes ===
    # Define the new column with null=True initially
    entity_type_field = CharField(null=True)
    watched_field = BooleanField(default=False)
    watch_count_field = IntegerField(default=0)

    run_migrations(
        migrator.add_column('media', 'entity_type', entity_type_field),
        migrator.add_column('media', 'watched', watched_field),
        migrator.add_column('media', 'watch_count', watch_count_field),
    )

    # Update all existing rows to set entity_type = "suggestion"
    # This needs to be done before making the column NOT NULL
    if Media.table_exists(): # Check if table exists, though it should in a migration context
        Media.update(entity_type="suggestion").execute()

    # Now alter the column to be NOT NULL
    run_migrations(
        migrator.add_not_null('media', 'entity_type')
    )

    # === WatchHistory table changes ===
    # Drop the WatchHistory table if it exists
    # This will be executed within the transaction and with PRAGMA foreign_keys=OFF for SQLite
    # by the migration runner.
    if WatchHistory.table_exists():
        # For PostgreSQL, if WatchHistory has foreign keys pointing to it from other tables,
        # cascade=True might be needed: WatchHistory.drop_table(cascade=True, safe=True)
        WatchHistory.drop_table(safe=True)

    # Recreate the WatchHistory table based on its current model definition
    database.create_tables([WatchHistory], safe=True)

def rollback(migrator: SchemaMigrator):
    # === Media table rollback ===
    # To properly rollback, first allow NULLs again, then drop the column
    run_migrations(
        migrator.drop_not_null('media', 'entity_type'), # Make it nullable before dropping
        migrator.drop_column('media', 'entity_type'),
        migrator.drop_column('media', 'watched'),
        migrator.drop_column('media', 'watch_count'),
    )

