import pytest
from unittest.mock import MagicMock, patch

from discovarr import Discovarr # Keep this for type hinting if needed
from services.models import LibraryUser, ItemsFiltered
from tests.unit.base.base_discovarr_tests import mocked_discovarr_instance # Import the new base fixture


def test_get_prompt_basic_scenario(mocked_discovarr_instance: Discovarr):
    dv = mocked_discovarr_instance
    
    # --- Configure mocks for this specific test ---
    # Settings:
    default_prompt_template = 'Test Prompt: Media={{ media_name }}, Limit={{ limit }}, Excludes={{ all_media }}, Favs={{ favorites }}, History={{ watch_history }}'
    test_specific_settings = {
        ("app", "default_prompt"): default_prompt_template,
        ("plex", "enabled"): True,
        ("jellyfin", "enabled"): True,
        ("plex", "enable_media"): True,
        ("jellyfin", "enable_media"): True,
        ("plex", "default_user"): None, # Test fetching for all Plex users
        ("jellyfin", "default_user"): None, # Test fetching for all Jellyfin users
        # Ensure default_prompt is also part of the side_effect if get_prompt relies on it
    }
    dv.default_prompt = default_prompt_template # Ensure dv.default_prompt is set for this test
    dv.settings.get.side_effect = lambda group, key, default=None: test_specific_settings.get((group, key), default)
    dv.plex_enable_media = True # Explicitly set for the test
    dv.jellyfin_enable_media = True # Explicitly set for the test
    dv.plex_enabled = True
    dv.jellyfin_enabled = True

    # Provider Data:
    dv.plex.get_all_items_filtered.return_value = ["Plex Movie A"]
    dv.plex.get_users.return_value = [LibraryUser(id="p_user1", name="PlexUser1", source_provider="plex")]
    dv.plex.get_favorites.return_value = [ItemsFiltered(name="PlexFav1", id="tmdb_pf1", type="movie", last_played_date="2023-01-01T00:00:00Z")]
    
    dv.jellyfin.get_all_items_filtered.return_value = ["Jellyfin Show B"]
    dv.jellyfin.get_users.return_value = [LibraryUser(id="j_user1", name="JellyfinUser1", source_provider="jellyfin")]
    dv.jellyfin.get_favorites.return_value = [ItemsFiltered(name="JellyfinFav1", id="tmdb_jf1", type="tv", last_played_date="2023-01-02T00:00:00Z")]

    # Database Data:
    dv.db.get_ignored_suggestions_titles.return_value = ["Ignored C"]
    dv.db.get_watch_history.return_value = [{"title": "Watched D"}] # Assumes structure from db method
    
    # --- Call the method under test ---
    prompt = dv.get_prompt(limit=5, media_name="Test Movie")

    # --- Assertions ---
    # Check for key parts of the prompt. Order of comma-separated items can vary.
    assert "Test Prompt: Media=Test Movie" in prompt
    assert "Limit=5" in prompt
    
    # Assert presence of individual excluded items
    assert "Ignored C" in prompt
    assert "Plex Movie A" in prompt
    assert "Jellyfin Show B" in prompt
    
    # Assert presence of individual favorite items
    assert "PlexFav1" in prompt
    assert "JellyfinFav1" in prompt
    
    assert "History=Watched D" in prompt # Assumes only one watched item for simplicity here
    
    # Verify mock calls
    dv.db.get_ignored_suggestions_titles.assert_called_once()
    dv.db.get_watch_history.assert_called_once_with(limit=None) # get_prompt fetches all history
    
    dv.plex.get_all_items_filtered.assert_called_once_with(attribute_filter="name")
    dv.plex.get_users.assert_called_once() # Called because default_user is None
    dv.plex.get_favorites.assert_called_once_with(user_id="p_user1") # Assuming it iterates
    
    dv.jellyfin.get_all_items_filtered.assert_called_once_with(attribute_filter="Name")
    dv.jellyfin.get_users.assert_called_once() # Called because default_user is None
    dv.jellyfin.get_favorites.assert_called_once_with(user_id="j_user1") # Assuming it iterates


def test_get_prompt_with_default_plex_user(mocked_discovarr_instance: Discovarr):
    dv = mocked_discovarr_instance # dv is already the mocked instance
    
    default_prompt_template = "Favs: {{ favorites }}"
    test_specific_settings = {
        ("app", "default_prompt"): default_prompt_template,
        ("plex", "enabled"): True,
        ("plex", "default_user"): "MyPlexUser",
        ("plex", "enable_media"): True,
        ("jellyfin", "enabled"): False, # Disable Jellyfin for this test
    }
    dv.default_prompt = default_prompt_template # Ensure dv.default_prompt is set for this test
    dv.settings.get.side_effect = lambda group, key, default=None: test_specific_settings.get((group, key), default)
    dv.plex_enabled = True
    dv.plex_enable_media = True # Explicitly set for the test
    dv.jellyfin_enabled = False

    mock_plex_user = LibraryUser(id="plex123", name="MyPlexUser", source_provider="plex")
    dv.plex.get_user_by_name.return_value = mock_plex_user
    dv.plex.get_favorites.return_value = [ItemsFiltered(name="PlexUserFav", id="tmdb_puf1", type="movie", last_played_date="2023-01-03T00:00:00Z")]

    prompt = dv.get_prompt(limit=3, media_name="Another Movie")

    assert "Favs: PlexUserFav" in prompt
    dv.plex.get_user_by_name.assert_called_once_with("MyPlexUser")
    dv.plex.get_favorites.assert_called_once_with(user_id="plex123")
    dv.jellyfin.get_all_items_filtered.assert_not_called() # Jellyfin is disabled


def test_get_prompt_custom_template_string(mocked_discovarr_instance: Discovarr):
    dv = mocked_discovarr_instance # dv is already the mocked instance
    
    # Ensure providers are disabled so they don't interfere if not explicitly mocked
    dv.plex_enabled = False
    dv.plex = None # Explicitly set provider instance to None
    dv.jellyfin_enabled = False
    dv.jellyfin = None # Explicitly set provider instance to None
    dv.settings.get.side_effect = lambda group, key, default=None: {
        ("plex", "enabled"): False, 
        ("plex", "enable_media"): False,
        ("jellyfin", "enabled"): False,
        ("jellyfin", "enable_media"): False,
        # No need to mock enable_history here as get_prompt uses db.get_watch_history
    }.get((group, key), default)


    dv.db.get_ignored_suggestions_titles.return_value = ["Ignored X"] # Set ignored media for the assertion
    dv.db.get_watch_history.return_value = [{"title": "Watched Y"}]

    custom_template = "Custom: {{ media_name }} | Exclude: {{ all_media }} | Favs: {{ favorites }} | History: {{ watch_history }}"
    prompt = dv.get_prompt(limit=10, media_name="Custom Media", template_string=custom_template)

    assert "Custom: Custom Media" in prompt
    assert "Exclude: Ignored X" in prompt # Only ignored items as providers are off
    assert "Favs:" in prompt
    assert "History: Watched Y" in prompt
