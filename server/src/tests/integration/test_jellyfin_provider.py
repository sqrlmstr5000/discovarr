import pytest
import os
from typing import List # For type hinting

from providers.jellyfin import JellyfinProvider
from services.models import ItemsFiltered, LibraryUser # Ensure LibraryUser is imported if not already
from tests.integration.base.base_live_library_provider_tests import BaseLiveLibraryProviderTests

# --- Fixtures for Jellyfin ---

@pytest.fixture(scope="module")
def live_jellyfin_url() -> str:
    """Retrieves Jellyfin URL from environment variable."""
    url = os.environ.get("JELLYFIN_TEST_URL")
    if not url:
        pytest.skip("JELLYFIN_TEST_URL environment variable not set. Skipping live Jellyfin tests.")
    return url

@pytest.fixture(scope="module")
def live_jellyfin_api_key() -> str:
    """Retrieves Jellyfin API Key from environment variable."""
    api_key = os.environ.get("JELLYFIN_TEST_API_KEY")
    if not api_key:
        pytest.skip("JELLYFIN_TEST_API_KEY environment variable not set. Skipping live Jellyfin tests.")
    return api_key

@pytest.mark.integration_live # Mark tests that hit the live API
class TestJellyfinProviderLive(BaseLiveLibraryProviderTests):
    """Groups live integration tests for JellyfinProvider."""

    # Override the live_provider fixture from the base class and make it module-scoped
    @pytest.fixture(scope="module")
    def live_provider(self, live_jellyfin_url: str, live_jellyfin_api_key: str) -> JellyfinProvider:
        """
        Provides a live instance of the JellyfinProvider, scoped for the module.
        """
        provider = JellyfinProvider(
            jellyfin_url=live_jellyfin_url,
            jellyfin_api_key=live_jellyfin_api_key
            # limit is optional and defaults in JellyfinProvider constructor
        )
        assert provider.jellyfin_url == live_jellyfin_url, "Provider URL should be set."
        return provider

    # Other tests like test_provider_name, test_get_users, test_get_user_by_name,
    # test_get_all_items_filtered_as_objects, and test_get_all_items_filtered_as_names
    # are inherited from BaseLiveLibraryProviderTests and should work as expected.