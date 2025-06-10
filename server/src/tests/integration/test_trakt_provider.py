import pytest
import os
import json
from datetime import datetime # For type checking Trakt object attributes

# Adjust these imports based on your project structure
from plugins.trakt import TraktProvider
from services.models import ItemsFiltered 
from trakt import Trakt
from trakt.objects.episode import Episode
from trakt.objects.movie import Movie
from trakt.objects.show import Show


# --- Fixtures ---

@pytest.fixture(scope="module")
def live_trakt_client_id() -> str:
    """Retrieves Trakt Client ID from environment variable."""
    client_id = os.environ.get("TRAKT_TEST_CLIENT_ID")
    if not client_id:
        pytest.skip("TRAKT_TEST_CLIENT_ID environment variable not set. Skipping live Trakt tests.")
    return client_id

@pytest.fixture(scope="module")
def live_trakt_client_secret() -> str:
    """Retrieves Trakt Client Secret from environment variable."""
    secret = os.environ.get("TRAKT_TEST_CLIENT_SECRET")
    if not secret:
        pytest.skip("TRAKT_TEST_CLIENT_SECRET environment variable not set. Skipping live Trakt tests.")
    return secret

@pytest.fixture(scope="module")
def live_trakt_redirect_uri() -> str:
    """Retrieves Trakt Redirect URI from environment variable, defaulting for device auth."""
    return os.environ.get("TRAKT_TEST_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

@pytest.fixture(scope="module")
def live_trakt_initial_authorization() -> dict:
    """
    Loads pre-obtained Trakt authorization details from an environment variable.
    The TRAKT_TEST_AUTH_JSON should be a JSON string containing the full authorization dict.
    """
    auth_json_str = os.environ.get("TRAKT_TEST_AUTH_JSON")
    if not auth_json_str:
        pytest.skip("TRAKT_TEST_AUTH_JSON environment variable not set. Skipping live Trakt tests.")
    try:
        auth_dict = json.loads(auth_json_str)
        required_keys = ["access_token", "refresh_token", "created_at", "expires_in", "token_type", "scope"]
        if not all(key in auth_dict for key in required_keys):
            pytest.fail(f"TRAKT_TEST_AUTH_JSON is missing one or more required keys: {required_keys}")
        return auth_dict
    except json.JSONDecodeError:
        pytest.fail("TRAKT_TEST_AUTH_JSON is not valid JSON.")
    return {} 

@pytest.fixture(scope="module")
def live_trakt_provider(live_trakt_client_id, live_trakt_client_secret, live_trakt_redirect_uri, live_trakt_initial_authorization) -> TraktProvider:
    """
    Initializes the TraktProvider with live credentials and pre-obtained authorization.
    This fixture assumes TraktProvider.__init__ has been modified to accept `initial_authorization`.
    """
    provider = TraktProvider(
        client_id=live_trakt_client_id,
        client_secret=live_trakt_client_secret,
        redirect_uri=live_trakt_redirect_uri,
        initial_authorization=live_trakt_initial_authorization # Pass the pre-obtained auth
    )
    
    assert provider.authorization is not None, "Provider authorization should be set via initial_authorization."
    #assert Trakt['oauth'].token is not None, "Trakt library should be configured with a token."
    return provider

# --- Test Cases ---

#@pytest.mark.integration_live # Mark tests that hit the live API
class TestTraktProviderLive:
    """Groups live integration tests for TraktProvider."""

    def test_get_users_live(self, live_trakt_provider: TraktProvider):
        """Tests fetching the authenticated user's details."""
        users = live_trakt_provider.get_users()
        assert users is not None, "get_users should return a list, not None"
        assert isinstance(users, list)
        assert len(users) > 0, "Expected at least one user (the authenticated user)"
        
        user = users[0]
        assert "Id" in user and isinstance(user["Id"], str), "User 'Id' (slug) should exist and be a string"
        assert "Name" in user and isinstance(user["Name"], str), "User 'Name' (username) should exist and be a string"

    def test_get_user_by_name_live(self, live_trakt_provider: TraktProvider):
        """Tests fetching a user by their name (should be the authenticated user)."""
        auth_user_list = live_trakt_provider.get_users()
        assert auth_user_list and len(auth_user_list) > 0, "Could not get authenticated user for this test"
        authenticated_username = auth_user_list[0]["Name"]

        user = live_trakt_provider.get_user_by_name(authenticated_username)
        assert user is not None, f"User '{authenticated_username}' should be found"
        assert user["Name"] == authenticated_username
        assert "Id" in user

        non_existent_user = live_trakt_provider.get_user_by_name("a_user_that_REALLY_does_not_exist_12345abc")
        assert non_existent_user is None, "Non-existent user should return None"

    def test_get_recently_watched_live(self, live_trakt_provider: TraktProvider):
        """Tests fetching recently watched items. Assumes the test account has some history."""
        users = live_trakt_provider.get_users()
        assert users and len(users) > 0
        user_id_slug = users[0]["Id"]

        watched_items = live_trakt_provider.get_recently_watched(user_id=user_id_slug, limit=5)
        assert watched_items is not None, "Expected recently watched items or an empty list"
        assert isinstance(watched_items, list)

        if watched_items:
            item = watched_items[0]
            assert type(item) in [Movie, Episode]
            assert hasattr(item, 'watched_at') and isinstance(item.watched_at, datetime)
        else:
            live_trakt_provider.logger.info("No recently watched items found for the test user. Test passed structurally.")

    def test_get_favorites_live(self, live_trakt_provider: TraktProvider):
        """Tests fetching favorite items (watchlist). Assumes the test account might have a watchlist."""
        users = live_trakt_provider.get_users()
        assert users and len(users) > 0
        user_id_slug = users[0]["Id"]

        favorite_items = live_trakt_provider.get_favorites(user_id=user_id_slug, limit=5)
        assert favorite_items is not None, "Expected favorite items or an empty list"
        assert isinstance(favorite_items, list)

        if favorite_items:
            item = favorite_items[0]
            assert isinstance(item, (Movie, Show)), "Favorite items should be Trakt Movie or Show objects"
            assert hasattr(item, 'title')
            assert hasattr(item, 'ids') and 'trakt' in item.ids
        else:
            live_trakt_provider.logger.info("No favorite items (watchlist) found for the test user. Test passed structurally.")

    def test_get_items_filtered_from_live_history(self, live_trakt_provider: TraktProvider):
        """Tests filtering of live recently watched items."""
        users = live_trakt_provider.get_users()
        assert users and len(users) > 0
        user_id_slug = users[0]["Id"]

        raw_watched_items = live_trakt_provider.get_recently_watched(user_id=user_id_slug, limit=10)
        assert raw_watched_items is not None
        
        if not raw_watched_items:
            pytest.skip("No recently watched items found on Trakt for filtering test.")

        filtered_items = live_trakt_provider.get_items_filtered(items=raw_watched_items, source_type="history")
        assert isinstance(filtered_items, list)
        
        if filtered_items:
            item = filtered_items[0]
            assert isinstance(item, ItemsFiltered)
            assert item.name is not None
            assert item.id is not None
            assert item.type in ['movie', 'tv', None] 
            assert hasattr(item, 'last_played_date')
            assert hasattr(item, 'play_count') 
            assert item.is_favorite is False # History items are not inherently favorites

    def test_get_all_items_filtered_live(self, live_trakt_provider: TraktProvider):
        """Tests fetching and filtering of all items (history + watchlist)."""
        filtered_items = live_trakt_provider.get_all_items_filtered()
        assert filtered_items is not None, "get_all_items_filtered should return a list or None, not an error"
        assert isinstance(filtered_items, list)
        
        if filtered_items:
            item = filtered_items[0]
            assert isinstance(item, ItemsFiltered)
            assert item.name is not None
            assert item.id is not None
            assert item.type in ['movie', 'tv', None]
            # Further checks can be done on is_favorite or last_played_date if specific data is expected
        else:
            live_trakt_provider.logger.info("No items returned from get_all_items_filtered. Test passed structurally.")

