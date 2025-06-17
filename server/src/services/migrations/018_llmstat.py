import peewee as pw
from peewee import *
from playhouse.migrate import migrate as run_migrations, SchemaMigrator
# Import necessary models and the database proxy
from services.models import SearchStat, LLMStat, database

def upgrade(migrator: SchemaMigrator):
    # === SearchStat table changes ===
    # Drop the SearchStat table if it exists
    # This will be executed within the transaction and with PRAGMA foreign_keys=OFF for SQLite
    # by the migration runner.
    if SearchStat.table_exists():
        # For PostgreSQL, if WatchHistory has foreign keys pointing to it from other tables,
        # cascade=True might be needed: WatchHistory.drop_table(cascade=True, safe=True)
        SearchStat.drop_table(safe=True)

    # Recreate the WatchHistory table based on its current model definition
    database.create_tables([LLMStat], safe=True)

def rollback(migrator: SchemaMigrator):
    if not SearchStat.table_exists():
        # For PostgreSQL, if WatchHistory has foreign keys pointing to it from other tables,
        # cascade=True might be needed: WatchHistory.drop_table(cascade=True, safe=True)
        database.create_tables([SearchStat], safe=True)

