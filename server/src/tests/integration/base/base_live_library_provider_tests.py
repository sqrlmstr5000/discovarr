# in a new file, e.g., tests/base/base_library_provider_tests.py
import pytest
from typing import List, Optional, Union
from services.models import LibraryUser, ItemsFiltered
from base.library_provider_base import LibraryProviderBase # Your abstract base class

class BaseLiveLibraryProviderTests:
    # This fixture must be overridden by concrete test classes
    @pytest.fixture
    def live_provider(self) -> LibraryProviderBase:
        """Provides a live instance of the library provider."""
        raise NotImplementedError("Subclasses must implement this fixture.")

    @pytest.fixture
    def valid_user_id(self, live_provider: LibraryProviderBase) -> str:
        """
        Provides a valid user ID for the specific provider.
        Subclasses might need to fetch this dynamically.
        """
        # Example: Fetch the first user; subclasses might need more specific logic
        users = live_provider.get_users()
        if not users:
            pytest.skip(f"No users found for provider {live_provider.name} to get a valid_user_id.")
        return users[0].id

    @pytest.fixture
    def valid_username(self, live_provider: LibraryProviderBase) -> str:
        """Provides a valid username for the specific provider."""
        users = live_provider.get_users()
        if not users:
            pytest.skip(f"No users found for provider {live_provider.name} to get a valid_username.")
        return users[0].name

    def test_provider_name(self, live_provider: LibraryProviderBase):
        assert isinstance(live_provider.name, str)
        assert len(live_provider.name) > 0

    def test_get_users(self, live_provider: LibraryProviderBase):
        users = live_provider.get_users()
        assert users is not None, "get_users should return a list or None"
        if users: # Okay if it's an empty list
            assert isinstance(users, list)
            for user in users:
                assert isinstance(user, LibraryUser)
                assert hasattr(user, 'id') # Check if the attribute exists
                # Allow id to be None, but if it's not None, check its type (e.g., str)
                if user.id is not None:
                    assert isinstance(user.id, str), f"User ID for {user.name} should be a string if not None, got {type(user.id)}"
                assert hasattr(user, 'name') and user.name is not None
                assert hasattr(user, 'source_provider') and user.source_provider == live_provider.name

    def test_get_user_by_name(self, live_provider: LibraryProviderBase, valid_username: str):
        user = live_provider.get_user_by_name(valid_username)
        # This assertion depends on valid_username actually existing for the provider
        if live_provider.get_users(): # Only assert if we could get users to begin with
             assert user is not None, f"User '{valid_username}' should be found for provider {live_provider.name}"
             if user:
                assert isinstance(user, LibraryUser)
                assert user.name == valid_username

        non_existent_user = live_provider.get_user_by_name("a_user_that_REALLY_does_not_exist_12345abc_xyz")
        assert non_existent_user is None, "Non-existent user should return None"

    def test_get_recently_watched(self, live_provider: LibraryProviderBase, valid_user_id: str):
        watched_items_raw = live_provider.get_recently_watched(user_id=valid_user_id, limit=1)
        assert watched_items_raw is not None, "Expected recently watched items (raw) or an empty list"
        assert isinstance(watched_items_raw, list)
        assert len(watched_items_raw) == 1, "Expected 1 item when limit is 1"
        if watched_items_raw:
            for item_dict in watched_items_raw:
                assert isinstance(item_dict, ItemsFiltered)
                # Add basic checks for expected keys if common across providers' raw output

    def test_get_recently_watched_all(self, live_provider: LibraryProviderBase, valid_user_id: str):
        watched_items_raw = live_provider.get_recently_watched(user_id=valid_user_id, limit=None)
        assert watched_items_raw is not None, "Expected recently watched items (raw) or an empty list"
        assert isinstance(watched_items_raw, list)
        assert len(watched_items_raw) > 1, "Expected a list of more than 1 items"
        if watched_items_raw:
            for item_dict in watched_items_raw:
                assert isinstance(item_dict, ItemsFiltered)
                # Add basic checks for expected keys if common across providers' raw output

    def test_get_favorites(self, live_provider: LibraryProviderBase, valid_user_id: str):
        # Similar to get_recently_watched, testing the List[Dict[str, Any]] contract
        favorite_items_raw = live_provider.get_favorites(user_id=valid_user_id, limit=5)
        assert favorite_items_raw is not None, "Expected favorite items (raw) or an empty list"
        assert isinstance(favorite_items_raw, list)
        if favorite_items_raw:
            for item_dict in favorite_items_raw:
                assert isinstance(item_dict, ItemsFiltered)

    def test_get_all_items_filtered_as_objects(self, live_provider: LibraryProviderBase):
        # Test when attribute_filter is None (should return List[ItemsFiltered])
        filtered_items = live_provider.get_all_items_filtered()
        assert filtered_items is not None
        assert isinstance(filtered_items, list)
        if filtered_items:
            for item in filtered_items:
                assert isinstance(item, ItemsFiltered)
                assert hasattr(item, 'name') and item.name is not None
                assert hasattr(item, 'id') # Ensure the attribute exists
                if item.id is not None: # If ID is present, check its type
                    assert isinstance(item.id, str), f"Item ID for '{item.name}' should be a string if not None, got {type(item.id)}"
                # ... other common ItemsFiltered attributes

    def test_get_all_items_filtered_as_names(self, live_provider: LibraryProviderBase):
        # Test when attribute_filter is "Name" (should return List[str])
        # Note: Ensure the attribute_filter value ("Name" or "name") is consistent.
        filtered_names = live_provider.get_all_items_filtered(attribute_filter="Name")
        assert filtered_names is not None
        assert isinstance(filtered_names, list)
        if filtered_names:
            for name in filtered_names:
                assert isinstance(name, str)
