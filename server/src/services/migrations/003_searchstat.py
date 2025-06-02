import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    """Set the search_id column in the searchstat table to allow NULLs."""
    run_migrations(
        migrator.drop_not_null('searchstat', 'search_id'), # 'search_id' is the typical column name for a ForeignKeyField named 'search'
    )

def downgrade(migrator: SchemaMigrator):
    """Revert SearchStat.search to NOT NULL (if possible and desired)."""
    # Note: Downgrading to NOT NULL might fail if there are existing NULL values.
    # You might need to handle or clean up NULLs before applying this.
    run_migrations(
        migrator.add_not_null('searchstat', 'search_id')
    )