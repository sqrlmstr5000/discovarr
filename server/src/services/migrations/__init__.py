import logging
from playhouse.migrate import SchemaMigrator # Generic migrator type
from peewee import Database as PeeweeDatabase # Generic Peewee Database type
from datetime import datetime

class Migration:
    def __init__(self, database: PeeweeDatabase, migrator: SchemaMigrator):
        self.logger = logging.getLogger(__name__)
        self.database = database
        self.migrator = migrator # Use the passed migrator instance
        
    def get_current_version(self) -> int:
        try:
            cursor = self.database.execute_sql(
                "SELECT version FROM migrations ORDER BY version DESC LIMIT 1"
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except:
            self.logger.warning("Could not get current version, resetting migrations table")
            return 0

    def set_version(self, version: int):
        self.database.execute_sql(
            "INSERT INTO migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now())
        )