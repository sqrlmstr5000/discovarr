import pytest
from unittest.mock import MagicMock, patch

from discovarr import Discovarr
from services.settings import SettingsService as ActualSettingsService
from services.database import Database as ActualDatabaseService
from providers.plex import PlexProvider as ActualPlexProvider
from providers.jellyfin import JellyfinProvider as ActualJellyfinProvider
from providers.trakt import TraktProvider as ActualTraktProvider
from services.image_cache import ImageCacheService as ActualImageCacheService
from services.radarr import Radarr as ActualRadarrService
from services.sonarr import Sonarr as ActualSonarrService
from providers.gemini import GeminiProvider as ActualGeminiProvider
from providers.ollama import OllamaProvider as ActualOllamaProvider
from services.tmdb import TMDB as ActualTMDBService

@pytest.fixture
def mocked_discovarr_instance(tmp_path):
    """
    Provides a Discovarr instance with its core dependencies (settings, db, providers, etc.)
    mocked. This fixture is intended for unit/integration tests of Discovarr methods
    that do not require live external service interactions.
    """
    temp_db_file = tmp_path / "test_discovarr_unit.db"

    # This mock handles SettingsService.get calls specifically during Discovarr.__init__
    def mock_settings_get_during_discovarr_init(group, key, default=None):
        return default

    # Patch all external service initializations and critical methods
    with patch.object(ActualSettingsService, '_initialize_settings', return_value=None), \
         patch.object(ActualSettingsService, 'get', side_effect=mock_settings_get_during_discovarr_init), \
         patch('providers.plex.PlexProvider.__init__', return_value=None), \
         patch('providers.jellyfin.JellyfinProvider.__init__', return_value=None), \
         patch('providers.trakt.TraktProvider.__init__', return_value=None), \
         patch('services.radarr.Radarr.__init__', return_value=None), \
         patch('services.sonarr.Sonarr.__init__', return_value=None), \
         patch('providers.gemini.GeminiProvider.__init__', return_value=None), \
         patch('providers.ollama.OllamaProvider.__init__', return_value=None), \
         patch('services.tmdb.TMDB.__init__', return_value=None), \
         patch('services.database.Database._run_migrations', return_value=None), \
         patch('services.image_cache.ImageCacheService.__init__', return_value=None):

        # Instantiate Discovarr, passing the temporary database path.
        # Discovarr.__init__ will call its self.db = Database(temp_db_file, ...)
        # which initializes the global Peewee database object.
        dv = Discovarr(db_path=str(temp_db_file))

    # After Discovarr is instantiated (its self.db is real but migrations are patched),
    # replace its attributes with MagicMocks for testing purposes.
    dv.settings = MagicMock(spec=ActualSettingsService)
    dv.db = MagicMock(spec=ActualDatabaseService)
    dv.plex = MagicMock(spec=ActualPlexProvider)
    dv.jellyfin = MagicMock(spec=ActualJellyfinProvider)
    dv.trakt = MagicMock(spec=ActualTraktProvider)
    dv.image_cache = MagicMock(spec=ActualImageCacheService)
    dv.radarr = MagicMock(spec=ActualRadarrService)
    dv.sonarr = MagicMock(spec=ActualSonarrService)
    dv.gemini = MagicMock(spec=ActualGeminiProvider)
    dv.ollama = MagicMock(spec=ActualOllamaProvider)
    dv.tmdb = MagicMock(spec=ActualTMDBService)

    # --- Setup default mock behaviors for the newly assigned MagicMocks ---
    default_settings_values_for_test = {
        ("app", "default_prompt"): "Default: {{ media_name }}", # Used by get_prompt
        # Add other settings as needed by the tests using this fixture
    }
    dv.settings.get.side_effect = lambda group, key, default=None: default_settings_values_for_test.get((group, key), default)

    # Default behaviors for db and providers (can be overridden in specific tests)
    dv.db.get_ignored_suggestions_titles.return_value = []
    dv.db.get_watch_history.return_value = []
    for provider_mock in [dv.plex, dv.jellyfin, dv.trakt]:
        provider_mock.get_all_items_filtered.return_value = []
        provider_mock.get_users.return_value = []
        provider_mock.get_user_by_name.return_value = None
        provider_mock.get_favorites.return_value = []

    # Set enabled flags based on how get_prompt checks them (instance attributes)
    # These will be typically overridden by individual tests.
    dv.plex_enabled = False
    dv.plex_enable_media = False
    dv.plex_enable_history = False

    dv.jellyfin_enabled = False
    dv.jellyfin_enable_media = False
    dv.jellyfin_enable_history = False

    dv.trakt_enabled = False
    dv.trakt_enable_media = False
    dv.trakt_enable_history = False

    return dv