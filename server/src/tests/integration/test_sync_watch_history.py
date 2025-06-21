import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from discovarr import Discovarr
from services.models import LibraryUser, ItemsFiltered
from services.database import Media, WatchHistory
from providers.jellyfin import JellyfinProvider
from providers.plex import PlexProvider
from providers.trakt import TraktProvider

# Mark this test as an integration test to be run with `pytest -m integration`
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def discovarr_instance():
    """
    Fixture to initialize a Discovarr instance for integration testing.
    It uses a test database path and yields the instance for use in tests.
    The database is cleaned up after the tests complete.
    """
    test_db_path = "/tmp/test_discovarr.db"  # Or wherever you want your test DB
    instance = Discovarr(db_path=test_db_path)
    yield instance  # Provide the instance to the test
    # Clean up: Close database connection and delete the test database file
    instance.db.cleanup()
    import os
    # Remove the main DB file and any associated WAL/SHM files
    db_files_to_remove = [test_db_path, f"{test_db_path}-wal", f"{test_db_path}-shm"]
    for f in db_files_to_remove:
        if os.path.exists(f):
            os.remove(f)


@pytest.mark.asyncio
async def test_sync_watch_history_jellyfin_only(discovarr_instance: Discovarr):
    """
    Tests sync_watch_history when only Jellyfin is enabled and has history.
    """
    # Sample data for mocking
    jellyfin_user = LibraryUser(id='jellyfin_user_123', name='JellyfinUser', source_provider='jellyfin')
    jellyfin_history_item = ItemsFiltered(id='12345', type='movie', name='Jellyfin Movie', last_played_date='2023-01-01T12:00:00Z', poster_url=None, is_favorite=False)

    # Mock the provider instance itself since it will be None by default
    mock_jellyfin_provider = MagicMock(spec=JellyfinProvider)
    mock_jellyfin_provider.get_users.return_value = [jellyfin_user]
    mock_jellyfin_provider.get_recently_watched.return_value = [jellyfin_history_item]

    # Mock providers and settings
    with patch.object(discovarr_instance, 'jellyfin_enabled', True), \
         patch.object(discovarr_instance, 'plex_enabled', False), \
         patch.object(discovarr_instance, 'trakt_enabled', False), \
         patch.object(discovarr_instance, 'jellyfin', mock_jellyfin_provider), \
         patch.object(discovarr_instance, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[jellyfin_history_item]) as mock_sync_to_db:

        # Call the sync method
        result = await discovarr_instance.sync_watch_history()

        # Assertions
        mock_jellyfin_provider.get_users.assert_called_once()
        # DB is empty, so limit should be None for full sync
        mock_jellyfin_provider.get_recently_watched.assert_called_once_with(user_id='jellyfin_user_123', limit=None)
        mock_sync_to_db.assert_called_once_with(
            user_name='JellyfinUser',
            user_id='jellyfin_user_123',
            recently_watched_items=[jellyfin_history_item],
            source='jellyfin'
        )
        
        assert isinstance(result, dict)
        assert 'JellyfinUser' in result
        assert result['JellyfinUser']['id'] == 'jellyfin_user_123'
        assert 'Jellyfin Movie' in result['JellyfinUser']['recent_titles']

@pytest.mark.asyncio
async def test_sync_watch_history_plex_only(discovarr_instance: Discovarr):
    """
    Tests sync_watch_history when only Plex is enabled and has history.
    """
    # Sample data for mocking
    plex_user = LibraryUser(id='plex_user_456', name='PlexUser', source_provider='plex')
    plex_history_item = ItemsFiltered(id='54321', type='tv', name='Plex Show', last_played_date='2023-02-01T12:00:00Z', poster_url=None, is_favorite=True)

    # Mock the provider instance itself since it will be None by default
    mock_plex_provider = MagicMock(spec=PlexProvider)
    mock_plex_provider.get_users.return_value = [plex_user]
    mock_plex_provider.get_recently_watched.return_value = [plex_history_item]

    # Mock providers and settings
    with patch.object(discovarr_instance, 'jellyfin_enabled', False), \
         patch.object(discovarr_instance, 'plex_enabled', True), \
         patch.object(discovarr_instance, 'trakt_enabled', False), \
         patch.object(discovarr_instance, 'plex', mock_plex_provider), \
         patch.object(discovarr_instance, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[plex_history_item]) as mock_sync_to_db:
        
        # Call the sync method
        result = await discovarr_instance.sync_watch_history()

        # Assertions
        mock_plex_provider.get_users.assert_called_once()
        mock_plex_provider.get_recently_watched.assert_called_once_with(user_id='plex_user_456', limit=None)
        mock_sync_to_db.assert_called_once_with(
            user_name='PlexUser',
            user_id='plex_user_456',
            recently_watched_items=[plex_history_item],
            source='plex'
        )
        
        assert isinstance(result, dict)
        assert 'PlexUser' in result
        assert result['PlexUser']['id'] == 'plex_user_456'
        assert 'Plex Show' in result['PlexUser']['recent_titles']

@pytest.mark.asyncio
async def test_sync_watch_history_trakt_only(discovarr_instance: Discovarr):
    """
    Tests sync_watch_history when only Trakt is enabled and has history.
    """
    # Sample data for mocking
    trakt_user = LibraryUser(id='trakt-user', name='TraktUser', source_provider='trakt')
    trakt_history_item = ItemsFiltered(id='99999', type='movie', name='Trakt Movie', last_played_date='2023-03-01T12:00:00Z', poster_url=None, is_favorite=False)

    # Mock the provider instance itself since it will be None by default
    mock_trakt_provider = MagicMock(spec=TraktProvider)
    mock_trakt_provider.get_users.return_value = [trakt_user]
    mock_trakt_provider.get_recently_watched.return_value = [trakt_history_item]

    # Mock providers and settings
    with patch.object(discovarr_instance, 'jellyfin_enabled', False), \
         patch.object(discovarr_instance, 'plex_enabled', False), \
         patch.object(discovarr_instance, 'trakt_enabled', True), \
         patch.object(discovarr_instance, 'trakt', mock_trakt_provider), \
         patch.object(discovarr_instance, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[trakt_history_item]) as mock_sync_to_db:

        # Call the sync method
        result = await discovarr_instance.sync_watch_history()

        # Assertions
        mock_trakt_provider.get_users.assert_called_once()
        mock_trakt_provider.get_recently_watched.assert_called_once_with(user_id='trakt-user', limit=None)
        mock_sync_to_db.assert_called_once_with(
            user_name='TraktUser',
            user_id='trakt-user',
            recently_watched_items=[trakt_history_item],
            source='trakt'
        )
        
        assert isinstance(result, dict)
        assert 'TraktUser' in result
        assert result['TraktUser']['id'] == 'trakt-user'
        assert 'Trakt Movie' in result['TraktUser']['recent_titles']

@pytest.mark.asyncio
async def test_sync_watch_history_to_db_new_item(discovarr_instance: Discovarr):
    """
    Tests the _sync_watch_history_to_db method with a new media item.
    Verifies that both Media and WatchHistory records are created correctly.
    """
    # 1. Setup
    # Clean up any previous test runs for this item to ensure idempotency
    with discovarr_instance.db.db.atomic():
        media_to_delete = Media.get_or_none(Media.tmdb_id == "12345")
        if media_to_delete:
            WatchHistory.delete().where(WatchHistory.media == media_to_delete.id).execute()
            media_to_delete.delete_instance()

    history_item = ItemsFiltered(
        id='12345', 
        type='movie', 
        name='Brand New Movie From Test', 
        last_played_date='2023-10-26T10:00:00Z', 
        poster_url='http://example.com/poster.jpg', 
        is_favorite=False
    )
    
    # Mock external calls within _sync_watch_history_to_db
    with patch.object(discovarr_instance.tmdb, 'get_media_detail', return_value={'poster_path': '/newposter.jpg', 'overview': 'A great movie.'}) as mock_tmdb, \
         patch.object(discovarr_instance, '_cache_image_if_needed', new_callable=AsyncMock, return_value='/cache/test_provider/12345.jpg') as mock_cache:

        # 2. Execute
        result = await discovarr_instance._sync_watch_history_to_db(
            user_name="DBTestUser",
            user_id="db_test_user_id",
            recently_watched_items=[history_item],
            source="test_provider"
        )

        # 3. Assert
        assert result == [history_item] # Method should return the items it processed
        mock_tmdb.assert_called_once_with(tmdb_id='12345', media_type='movie')
        mock_cache.assert_called_once_with('http://example.com/poster.jpg', 'test_provider', '12345')

        # Verify database state
        media_entry = Media.get_or_none(Media.tmdb_id == '12345')
        assert media_entry is not None
        assert media_entry.title == 'Brand New Movie From Test'
        assert media_entry.source_provider == 'test_provider'
        assert media_entry.watched is True
        assert media_entry.watch_count == 1
        assert media_entry.poster_url == '/cache/test_provider/12345.jpg'
        
        history_entries = discovarr_instance.db.get_watch_history(media_id=media_entry.id)
        assert len(history_entries) == 1
        assert history_entries[0]['watched_by'] == 'DBTestUser'
        expected_dt = datetime.fromisoformat('2023-10-26T10:00:00').replace(tzinfo=None) # Should be naive UTC
        assert history_entries[0]['last_played_date'] == expected_dt

@pytest.mark.asyncio
async def test_sync_watch_history_to_db_existing_item(discovarr_instance: Discovarr):
    """
    Tests the _sync_watch_history_to_db method with an existing media item.
    Verifies that the existing Media record is updated and a new WatchHistory record is added.
    """
    # 1. Setup: Create an existing media item
    with discovarr_instance.db.db.atomic():
        media_to_delete = Media.get_or_none(Media.tmdb_id == "67890")
        if media_to_delete:
            WatchHistory.delete().where(WatchHistory.media == media_to_delete.id).execute()
            media_to_delete.delete_instance()

    media_pk = discovarr_instance.db.create_media({
        "title": "Existing Movie In DB", "tmdb_id": "67890", "media_type": "movie",
        "entity_type": "library", "watch_count": 1, "watched": True
    })
    assert media_pk is not None

    history_item_to_sync = ItemsFiltered(
        id='67890', type='movie', name='Existing Movie In DB', # Name must match for lookup
        last_played_date='2023-10-27T11:00:00Z', poster_url=None, is_favorite=False
    )

    # Mock external calls (should not be called for existing media)
    with patch.object(discovarr_instance.tmdb, 'get_media_detail') as mock_tmdb, \
         patch.object(discovarr_instance, '_cache_image_if_needed') as mock_cache:

        # 2. Execute
        result = await discovarr_instance._sync_watch_history_to_db(
            user_name="AnotherUser", user_id="another_user_id",
            recently_watched_items=[history_item_to_sync], source="another_provider"
        )

        # 3. Assert
        assert result == [history_item_to_sync]
        mock_tmdb.assert_not_called()
        mock_cache.assert_not_called()

        media_entry = Media.get_or_none(Media.id == media_pk)
        assert media_entry is not None
        assert media_entry.watch_count == 2 # Incremented from 1
        assert media_entry.watched is True