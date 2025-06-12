import pytest
import os
from typing import List # For type hinting

from providers.plex import PlexProvider
from services.models import ItemsFiltered, LibraryUser 
from tests.integration.base.base_live_library_provider_tests import BaseLiveLibraryProviderTests

# --- Fixtures for Plex ---

@pytest.fixture(scope="module")
def live_plex_url() -> str: 
    """Retrieves Plex URL from environment variable."""
    url = os.environ.get("PLEX_TEST_URL")
    if not url:
        pytest.skip("PLEX_TEST_URL environment variable not set. Skipping live Plex tests.")
    return url

@pytest.fixture(scope="module")
def live_plex_api_key() -> str:
    """Retrieves Plex API Key (Token) from environment variable."""
    api_key = os.environ.get("PLEX_TEST_API_KEY") # Using API_KEY for consistency, though it's a token for Plex
    if not api_key:
        pytest.skip("PLEX_TEST_API_KEY environment variable not set. Skipping live Plex tests.")
    return api_key

@pytest.mark.integration_live # Mark tests that hit the live API
class TestPlexProviderLive(BaseLiveLibraryProviderTests):
    """Groups live integration tests for PlexProvider."""

    # Override the live_provider fixture from the base class and make it module-scoped
    @pytest.fixture(scope="module")
    def live_provider(self, live_plex_url: str, live_plex_api_key: str) -> PlexProvider:
        """
        Provides a live instance of the PlexProvider, scoped for the module.
        """
        provider = PlexProvider(
            plex_url=live_plex_url,
            plex_api_key=live_plex_api_key
            # limit is optional and defaults in PlexProvider constructor
        )
        assert provider.server is not None, "Plex server should be connected."
        return provider

    # All tests (test_provider_name, test_get_users, test_get_user_by_name,
    # test_get_recently_watched, test_get_favorites,
    # test_get_all_items_filtered_as_objects, and test_get_all_items_filtered_as_names)
    # are inherited from BaseLiveLibraryProviderTests and should work as expected
    # if PlexProvider correctly implements the LibraryProviderBase interface.