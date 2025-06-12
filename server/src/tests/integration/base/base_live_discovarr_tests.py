import pytest
from unittest.mock import MagicMock, patch

from discovarr import Discovarr
from services.settings import SettingsService # Import for spec
from services.database import Database as ActualDatabaseService # For spec
# Need to import actual provider classes for spec
from providers.plex import PlexProvider as ActualPlexProvider
from providers.jellyfin import JellyfinProvider as ActualJellyfinProvider
from providers.trakt import TraktProvider as ActualTraktProvider
from services.image_cache import ImageCacheService as ActualImageCacheService # For spec

@pytest.fixture
def mocked_discovarr_instance(tmp_path):
    """
    Provides a Discovarr instance with its core dependencies (settings, db, providers)
    mocked. This fixture is intended for unit/integration tests of Discovarr methods
    that do not require live external service interactions.
    """
    temp_db_file = tmp_path / "test_discovarr_unit.db"

    def mock_settings_get_during_discovarr_init(group, key, default=None):
        if group == "app" and key == "backup_before_upgrade":
            return True
        return default

    with patch.object(SettingsService, '_initialize_settings', return_value=None), \
         patch.object(SettingsService, 'get', side_effect=mock_settings_get_during_discovarr_init), \
         patch('plugins.plex.PlexProvider.__init__', return_value=None), \
         patch('plugins.jellyfin.JellyfinProvider.__init__', return_value=None), \
         patch('plugins.trakt.TraktProvider.__init__', return_value=None), \
         patch('services.radarr.Radarr.__init__', return_value=None), \
         patch('services.sonarr.Sonarr.__init__', return_value=None), \
         patch('plugins.gemini.GeminiProvider.__init__', return_value=None), \
         patch('plugins.ollama.OllamaProvider.__init__', return_value=None), \
         patch('services.tmdb.TMDB.__init__', return_value=None), \
         patch('services.database.Database._run_migrations', return_value=None), \
         patch('services.image_cache.ImageCacheService.__init__', return_value=None):
        # Instantiate Discovarr, passing the temporary database path.
        # This relies on Discovarr.__init__ being modified to accept db_path.
        dv = Discovarr(db_path=str(temp_db_file))

    # Replace actual services with MagicMocks for testing purposes
    dv.settings = MagicMock(spec=SettingsService)
    dv.db = MagicMock(spec=ActualDatabaseService)
    dv.plex = MagicMock(spec=ActualPlexProvider)
    dv.jellyfin = MagicMock(spec=ActualJellyfinProvider)
    dv.trakt = MagicMock(spec=ActualTraktProvider)
    dv.image_cache = MagicMock(spec=ActualImageCacheService) # Mock image_cache service

    # --- Setup default mock behaviors for the test's mocks ---
    default_settings_values_for_test = {
        ("app", "default_prompt"): "Default: {{ media_name }}",
        ("plex", "enabled"): False,
        ("jellyfin", "enabled"): False,
        ("trakt", "enabled"): False,
        ("plex", "default_user"): None,
        ("jellyfin", "default_user"): None,
    }
    dv.settings.get.side_effect = lambda group, key, default=None: default_settings_values_for_test.get((group, key), default)

    dv.db.get_ignored_media_titles.return_value = []
    dv.db.get_watch_history.return_value = []

    for provider_mock in [dv.plex, dv.jellyfin, dv.trakt]:
        provider_mock.get_all_items_filtered.return_value = []
        provider_mock.get_users.return_value = []
        provider_mock.get_user_by_name.return_value = None
        provider_mock.get_favorites.return_value = []

    dv.plex_enabled = default_settings_values_for_test[("plex", "enabled")]
    dv.jellyfin_enabled = default_settings_values_for_test[("jellyfin", "enabled")]
    dv.trakt_enabled = default_settings_values_for_test[("trakt", "enabled")]

    return dv