import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    run_migrations(
        migrator.rename_column('search', 'query', 'prompt'),
    )

def downgrade(migrator: SchemaMigrator):
    # Note: Downgrading to NOT NULL might fail if there are existing NULL values.
    # You might need to handle or clean up NULLs before applying this.
    run_migrations(
        migrator.rename_column('media', 'prompt`', 'genre'),
    )