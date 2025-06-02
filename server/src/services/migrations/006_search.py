import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    kwargs = pw.CharField(null=True)

    run_migrations(
        migrator.add_column('search', 'kwargs', kwargs),
    )

def rollback(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('search', 'kwargs'),
    )

