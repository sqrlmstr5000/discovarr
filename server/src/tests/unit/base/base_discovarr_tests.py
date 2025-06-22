import pytest
from unittest.mock import MagicMock, patch

from discovarr import Discovarr
from services.settings import SettingsService as ActualSettingsService
from services.database import Database as ActualDatabaseService
from providers.plex import PlexProvider as ActualPlexProvider
from providers.jellyfin import JellyfinProvider as ActualJellyfinProvider
from providers.trakt import TraktProvider as ActualTraktProvider
from services.image_cache import ImageCacheService as ActualImageCacheService
from providers.radarr import RadarrProvider as ActualRadarrService
from providers.sonarr import SonarrProvider as ActualSonarrService
from providers.gemini import GeminiProvider as ActualGeminiProvider
from providers.ollama import OllamaProvider as ActualOllamaProvider
from services.tmdb import TMDB as ActualTMDBService
from services.llm import LLMService as ActualLLMService # Import LLMService

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
        # Ensure Radarr (and other critical services) get their minimal config
        # during the initial Discovarr instantiation.
        if group == "radarr" and key == "url":
            return "http://mockradarr.test.init"
        if group == "radarr" and key == "api_key":
            return "mockapikey.init"
        if group == "radarr" and key == "root_dir_path":
            return "/mock/radarr/root.init"
        # Add similar for Sonarr
        if group == "sonarr" and key == "url":
            return "http://mocksonarr.test.init"
        if group == "sonarr" and key == "api_key":
            return "mockapikey.init"
        if group == "sonarr" and key == "root_dir_path":
            return "/mock/sonarr/root.init"
        # Add for Plex, Jellyfin, Trakt if they are to be initialized as mocks by default
        if group == "plex" and key == "enabled": return True
        if group == "plex" and key == "url": return "http://mockplex.init"
        if group == "plex" and key == "api_key": return "mockplexkey.init"
        if group == "plex" and key == "enable_media": return True  # For LLMService init
        if group == "plex" and key == "enable_history": return True # For LLMService init

        if group == "jellyfin" and key == "enabled": return True
        if group == "jellyfin" and key == "url": return "http://mockjellyfin.init"
        if group == "jellyfin" and key == "api_key": return "mockjellyfinkey.init"
        if group == "jellyfin" and key == "enable_media": return True # For LLMService init
        if group == "jellyfin" and key == "enable_history": return True # For LLMService init

        if group == "trakt" and key == "enabled": return True
        if group == "trakt" and key == "client_id": return "mocktraktclientid.init"
        if group == "trakt" and key == "client_secret": return "mocktraktclientsecret.init"
        if group == "trakt" and key == "enable_media": return True # For LLMService init
        if group == "trakt" and key == "enable_history": return True # For LLMService init

        if group == "gemini" and key == "enabled": return True # For LLMService init
        if group == "ollama" and key == "enabled": return True # For LLMService init
        return default

    # Patch all external service initializations and critical methods
    with patch.object(ActualSettingsService, '_initialize_settings', return_value=None), \
         patch.object(ActualSettingsService, 'get', side_effect=mock_settings_get_during_discovarr_init), \
         patch('discovarr.PlexProvider', new_callable=MagicMock) as MockPlexProviderClass, \
         patch('discovarr.JellyfinProvider', new_callable=MagicMock) as MockJellyfinProviderClass, \
         patch('discovarr.TraktProvider', new_callable=MagicMock) as MockTraktProviderClass, \
         patch('discovarr.RadarrProvider', new_callable=MagicMock) as MockRadarrClass, \
         patch('discovarr.SonarrProvider', new_callable=MagicMock) as MockSonarrClass, \
         patch('discovarr.GeminiProvider', new_callable=MagicMock) as MockGeminiProviderClass, \
         patch('discovarr.OllamaProvider', new_callable=MagicMock) as MockOllamaProviderClass, \
         patch('discovarr.TMDB', new_callable=MagicMock) as MockTMDBClass, \
         patch('services.database.Database._run_migrations', return_value=None), \
         patch('services.image_cache.ImageCacheService.__init__', return_value=None):

        dv = Discovarr(db_path=str(temp_db_file))

        # After Discovarr is instantiated (its self.db is real but migrations are patched),
        # replace its attributes with MagicMocks for testing purposes.
        # These will be the mocks the tests interact with directly.
        # If a test calls dv.reload_configuration(), and the class patches above are effective
        # (due to `yield dv` happening within this `with` block),
        # then attributes like dv.plex will be re-assigned to new MagicMock instances (from the mocked classes).
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
        dv.llm_service = MagicMock(spec=ActualLLMService)

        # --- Setup default mock behaviors for the newly assigned MagicMocks ---
        # This side_effect will be used by tests unless they override it.
        default_settings_values_for_test = {
            ("app", "default_prompt"): "Default: {{ media_name }}",
            ("radarr", "url"): "http://mockradarr:7878",
            ("radarr", "api_key"): "mock_radarr_key",
            ("radarr", "root_dir_path"): "/mock/radarr/root",
            ("sonarr", "url"): "http://mocksonarr:7878",
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("plex", "enabled"): True, ("plex", "url"): "http://mockplex", ("plex", "api_key"): "mockplexkey",
            ("plex", "enable_history"): True, ("plex", "enable_media"): True,
            ("jellyfin", "enabled"): True, ("jellyfin", "url"): "http://mockjellyfin", ("jellyfin", "api_key"): "mockjellyfinkey",
            ("jellyfin", "enable_history"): True, ("jellyfin", "enable_media"): True,
            ("trakt", "enabled"): True, ("trakt", "client_id"): "mocktraktclientid", ("trakt", "client_secret"): "mocktraktclientsecret",
            ("trakt", "enable_history"): True, ("trakt", "enable_media"): True,
            ("gemini", "enabled"): True, ("gemini", "api_key"): "mockgeminikey",
            ("ollama", "enabled"): True, ("ollama", "base_url"): "http://mockollama",
        }
        dv.settings.get.side_effect = lambda group, key, default=None: default_settings_values_for_test.get((group, key), default)

        # Default behaviors for db and providers (can be overridden in specific tests)
        dv.db.get_ignored_suggestions_titles.return_value = []
        dv.db.get_watch_history.return_value = []
        # Ensure these are the MagicMock instances assigned above
        for provider_mock in [dv.plex, dv.jellyfin, dv.trakt]:
            if provider_mock: # Should always be true as they are assigned above
                provider_mock.get_all_items_filtered.return_value = []
                provider_mock.get_users.return_value = []
                provider_mock.get_user_by_name.return_value = None
                provider_mock.get_favorites.return_value = []

        # The Discovarr instance's actual enabled flags (e.g., dv.plex_enabled)
        # will be set by its reload_configuration method based on the settings.
        # No need to manually set them to False here.

        yield dv # Yield dv from *within* the 'with patch(...)' block