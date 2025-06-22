import pytest
from unittest.mock import patch

from discovarr import Discovarr
from services.models import Settings

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


def test_env_variable_overwrites_default_on_creation(tmp_path, monkeypatch):
    """
    Tests that an environment variable correctly overwrites a default setting
    during the initial settings creation in a fresh database.
    """
    # 1. Setup: Set environment variable and prepare a temporary database path.
    test_db_path = tmp_path / "test_settings_env_creation.db"
    expected_url = "http://my-custom-jellyfin:8096"
    monkeypatch.setenv("JELLYFIN_URL", expected_url)

    # Patch _validate_configuration to prevent it from raising errors about other
    # missing settings, allowing us to focus only on the settings initialization logic.
    with patch('discovarr.Discovarr._validate_configuration', return_value=None):
        # 2. Execute: Initialize Discovarr, which triggers the settings initialization.
        discovarr_instance = Discovarr(db_path=str(test_db_path))

    # 3. Assert: Check the value in the database.
    # The database connection is managed by the Discovarr instance's db object.
    # We can query the Settings model directly.
    jellyfin_url_setting = Settings.get_or_none(
        (Settings.group == "jellyfin") & (Settings.name == "url")
    )

    assert jellyfin_url_setting is not None, "The 'jellyfin.url' setting should have been created."
    assert jellyfin_url_setting.value == expected_url, "The setting value should match the environment variable."

    # Clean up the instance to close the DB connection.
    discovarr_instance.db.cleanup()


def test_env_variable_overwrites_existing_db_value(tmp_path, monkeypatch):
    """
    Tests that an environment variable correctly overwrites an existing setting
    value in the database when the application starts up.
    """
    # 1. Setup: Prepare a temporary database path and initialize Discovarr once
    # to create the initial settings with default values.
    test_db_path = tmp_path / "test_settings_env_overwrite.db"

    with patch('discovarr.Discovarr._validate_configuration', return_value=None):
        discovarr_instance_1 = Discovarr(db_path=str(test_db_path))

    # Verify the initial default value is in the database.
    initial_setting = Settings.get((Settings.group == "jellyfin") & (Settings.name == "url"))
    assert initial_setting.value == "http://jellyfin:8096", "Initial value should be the default."

    # Clean up the first instance to release the DB file lock.
    discovarr_instance_1.db.cleanup()

    # 2. Execute: Set the environment variable and re-initialize Discovarr.
    expected_url = "http://my-overwritten-jellyfin:8096"
    monkeypatch.setenv("JELLYFIN_URL", expected_url)

    with patch('discovarr.Discovarr._validate_configuration', return_value=None):
        discovarr_instance_2 = Discovarr(db_path=str(test_db_path))

    # 3. Assert: Check that the value in the database has been updated.
    updated_setting = Settings.get((Settings.group == "jellyfin") & (Settings.name == "url"))

    assert updated_setting is not None, "The setting should still exist."
    assert updated_setting.value == expected_url, "The setting value should have been overwritten by the environment variable."

    # Clean up the second instance.
    discovarr_instance_2.db.cleanup()