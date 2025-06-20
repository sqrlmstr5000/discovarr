import pytest
import os
import logging
from pathlib import Path
from peewee import PeeweeException, PostgresqlDatabase

from services.database import Database
from services.models import Settings, database as db_proxy, MODELS, Media, MediaResearch
from services.settings import SettingsService
from services.research import ResearchService

# Configure basic logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Test Configuration ---
# IMPORTANT: These should point to a TEST PostgreSQL instance and database.
# DO NOT run these tests against a production database.
TEST_PG_HOST = os.environ.get("POSTGRES_TEST_HOST", "localhost")
TEST_PG_PORT = os.environ.get("POSTGRES_TEST_PORT", "5432")
TEST_PG_USER = os.environ.get("POSTGRES_TEST_USER", "testuser")
TEST_PG_PASSWORD = os.environ.get("POSTGRES_TEST_PASSWORD", "testpassword")
TEST_PG_DBNAME = os.environ.get("POSTGRES_TEST_DBNAME", "discovarr_test_db")

@pytest.fixture(scope="function")
def postgres_db_setup(monkeypatch, tmp_path: Path, caplog):
    """
    Fixture to set up a PostgreSQL database for testing.
    It sets environment variables for PostgreSQL connection,
    initializes the database, creates tables, and cleans up afterwards.
    It also monkeypatches pathlib.Path to redirect "/backups" to a temporary directory.
    """
    # Set caplog level early to capture logs from Database initialization
    caplog.set_level(logging.INFO)

    temp_sqlite_db_for_fallback = tmp_path / "dummy_sqlite_for_pg_test.db"
    temp_backup_dir_for_test = tmp_path / "test_fixture_backups_pg"
    
    # Monkeypatch pathlib.Path.__init__ to redirect "/backups"
    original_path_init = Path.__init__

    def mocked_path_init(self_path, *args, **kwargs):
        if args and str(args[0]) == "/backups":
            # Call original __init__ with the temporary backup path
            original_path_init(self_path, temp_backup_dir_for_test)
            # BackupService will call mkdir on this path, so we don't strictly need to do it here,
            # but it's good practice if the patch needs to ensure existence.
            # temp_backup_dir_for_test.mkdir(parents=True, exist_ok=True)
        else:
            original_path_init(self_path, *args, **kwargs)

    monkeypatch.setattr(Path, "__init__", mocked_path_init)

    monkeypatch.setenv("DISCOVARR_DATABASE", "postgres")
    monkeypatch.setenv("POSTGRES_HOST", TEST_PG_HOST)
    monkeypatch.setenv("POSTGRES_PORT", TEST_PG_PORT)
    monkeypatch.setenv("POSTGRES_USER", TEST_PG_USER)
    monkeypatch.setenv("POSTGRES_PASSWORD", TEST_PG_PASSWORD)
    monkeypatch.setenv("POSTGRES_DBNAME", TEST_PG_DBNAME)

    # Ensure the test database exists or can be created
    # This part is tricky as Database.__init__ tries to create it.
    # For a robust test, the test DB should ideally be managed externally
    # or by a more sophisticated fixture.

    db_instance = None
    try:
        # Initialize Database, which connects and creates tables
        # The Database class itself will attempt to create the DB if it doesn't exist.
        db_instance = Database(db_path=str(temp_sqlite_db_for_fallback))
        
        # Ensure we are connected to Postgres
        if db_instance.db_type != "postgres":
            pytest.skip("PostgreSQL not configured or connection failed, skipping test.")

        # At this point, tables should be created by Database.__init__
        # including the Settings table.
        # SettingsService._initialize_settings() is called by Discovarr,
        # but Database._run_migrations and _add_default_tasks might interact with settings.
        # For this test, we'll directly initialize settings after DB setup.
        settings_service = SettingsService()
        settings_service._initialize_settings()

        yield db_instance

    except PeeweeException as e:
        logger.error(f"PeeweeException during PostgreSQL test setup: {e}", exc_info=True)
        pytest.skip(f"Skipping PostgreSQL test due to PeeweeException: {e}")
    except RuntimeError as e: # Catch RuntimeError from Database connection failure
        logger.error(f"RuntimeError during PostgreSQL test setup: {e}", exc_info=True)
        pytest.skip(f"Skipping PostgreSQL test due to RuntimeError: {e}")
    if db_instance and db_proxy.obj:
        try:
            # Connect to a maintenance database (e.g., 'postgres') to drop the test database
            maintenance_db_conn = None
            try:
                maintenance_db_conn = PostgresqlDatabase(
                    "postgres",  # Or 'template1'
                    user=TEST_PG_USER,
                    password=TEST_PG_PASSWORD,
                    host=TEST_PG_HOST,
                    port=int(TEST_PG_PORT) # Ensure port is an integer
                )
                maintenance_db_conn.connect()
                # Terminate other connections to the database before dropping
                # This might require superuser privileges or specific grants for the test user.
                # Use with caution and ensure the test user has minimal necessary privileges.
                maintenance_db_conn.execute_sql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{TEST_PG_DBNAME}' AND pid <> pg_backend_pid();")
                maintenance_db_conn.execute_sql(f"DROP DATABASE IF EXISTS \"{TEST_PG_DBNAME}\";")
                logger.info(f"Successfully dropped PostgreSQL test database: {TEST_PG_DBNAME}")
            except Exception as drop_db_e:
                logger.error(f"Error dropping PostgreSQL test database '{TEST_PG_DBNAME}': {drop_db_e}", exc_info=True)
            finally:
                if maintenance_db_conn and not maintenance_db_conn.is_closed():
                    maintenance_db_conn.close()
                    logger.info("Closed connection to maintenance database.")
        except Exception as cleanup_e:
            logger.error(f"Error during PostgreSQL test cleanup (table drop or initial close): {cleanup_e}", exc_info=True)

def test_postgres_settings_initialization(postgres_db_setup):
    """
    Tests that default settings are initialized in the PostgreSQL database.
    """
    db_instance = postgres_db_setup # Get the initialized Database instance from the fixture
    assert db_instance.db_type == "postgres", "Database type should be PostgreSQL"

    # Check if a known default setting exists
    app_setting = Settings.get_or_none((Settings.group == "app") & (Settings.name == "recent_limit"))
    assert app_setting is not None, "Default 'app.recent_limit' setting should exist"
    assert app_setting.value == str(SettingsService.DEFAULT_SETTINGS["app"]["recent_limit"]["value"]), \
        "Default 'app.recent_limit' value should match"

    logger.info("PostgreSQL settings initialization test passed.")

@pytest.mark.integration_live # Mark this as a live integration test
def test_postgres_backup(postgres_db_setup):
    """
    Tests that the PostgreSQL database can be backed up using BackupService.
    """
    db_instance = postgres_db_setup # Get the initialized Database instance from the fixture
    assert db_instance.db_type == "postgres", "Database type should be PostgreSQL for backup test"

    backup_path_str = db_instance.backup_service.backup_db(name="test_backup")

    assert backup_path_str is not None, "Backup should return a valid path on success"
    assert Path(backup_path_str).exists(), "Backup file should exist at the returned path"
