import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from pathlib import Path
import aiohttp
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
        mock_cache.assert_called_once_with(
            image_url='http://example.com/poster.jpg',
            provider_name='test_provider',
            item_id='12345',
            media_type='movie'
        )

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

@pytest.mark.asyncio
async def test_reload_image_cache(discovarr_instance: Discovarr, tmp_path: Path, monkeypatch):
    """
    Integration test for reload_image_cache method.
    It covers scenarios like re-caching missing images, skipping existing ones,
    handling download errors, and updating database paths.
    """
    # 1. Setup
    # Setup a temporary cache directory for this test
    temp_cache_dir = tmp_path / "image_cache"
    temp_cache_dir.mkdir()
    monkeypatch.setattr(discovarr_instance.image_cache, 'cache_base_dir', temp_cache_dir)
    # Also need to ensure the subdirs exist, as the service does in its init
    (temp_cache_dir / 'movie').mkdir()
    (temp_cache_dir / 'tv').mkdir()

    # Clean up DB to ensure a clean slate
    with discovarr_instance.db.db.atomic():
        WatchHistory.delete().execute()
        Media.delete().execute()

    # Mock image data and URLs
    fake_image_data = b'this is a fake jpeg'
    good_url_1 = "http://example.com/good-poster-1.jpg"
    good_url_2 = "http://example.com/good-poster-2.png"
    good_url_3 = "http://example.com/good-poster-3.jpg"
    good_url_4 = "http://example.com/good-poster-4.jpg"
    bad_url = "http://example.com/bad-poster.jpg"

    # --- Populate DB with test cases ---
    # Case 1: Needs re-caching.
    media_to_recache_pk = discovarr_instance.db.create_media({
        "title": "Movie to Re-cache", "tmdb_id": "111", "media_type": "movie", "entity_type": "library",
        "poster_url_source": good_url_1, "poster_url": None, "source_provider": "test"
    })

    # Case 2: Already cached and correct in DB. Should be skipped.
    media_cached_pk = discovarr_instance.db.create_media({
        "title": "Movie Already Cached", "tmdb_id": "222", "media_type": "movie", "entity_type": "library",
        "poster_url_source": good_url_2, "poster_url": "movie/222.png", "source_provider": "test"
    })
    (temp_cache_dir / "movie" / "222.png").write_bytes(fake_image_data)

    # Case 3: Bad source URL, should fail.
    media_bad_url_pk = discovarr_instance.db.create_media({
        "title": "Movie with Bad URL", "tmdb_id": "333", "media_type": "movie", "entity_type": "library",
        "poster_url_source": bad_url, "poster_url": None, "source_provider": "test"
    })

    # Case 4: No source URL, should be skipped.
    discovarr_instance.db.create_media({
        "title": "Movie with No Source URL", "tmdb_id": "444", "media_type": "movie", "entity_type": "library",
        "poster_url_source": None, "poster_url": None, "source_provider": "test"
    })

    # Case 5: DB path needs update. File exists, but DB path is wrong. Should be skipped (and fixed).
    media_db_update_pk = discovarr_instance.db.create_media({
        "title": "Movie needing DB update", "tmdb_id": "555", "media_type": "movie", "entity_type": "library",
        "poster_url_source": good_url_3, "poster_url": "wrong/path/555.jpg", "source_provider": "test"
    })
    (temp_cache_dir / "movie" / "555.jpg").write_bytes(fake_image_data)

    # Case 6: Old cache format needs migration. Should be re-cached.
    media_old_format_pk = discovarr_instance.db.create_media({
        "title": "Movie with old cache format", "tmdb_id": "666", "media_type": "movie", "entity_type": "library",
        "poster_url_source": good_url_4, "poster_url": "test_666.jpg", "source_provider": "test"
    })
    old_cached_file_path = temp_cache_dir / "test_666.jpg"
    old_cached_file_path.write_bytes(fake_image_data)

    # Mock aiohttp.ClientSession.get to simulate network requests
    def mock_get_side_effect(url, **kwargs):
        """
        This side_effect function for aiohttp.ClientSession.get returns an
        AsyncMock that behaves like an async context manager. This is what
        `async with` expects.
        """
        # This is the object that will be yielded by the context manager (`response`)
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)

        if url == bad_url:
            mock_response.status = 404
            # Configure raise_for_status to raise an error, as the real one would
            mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(MagicMock(), (), status=404)
        else:  # good URLs
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None  # Does not raise

            # Mock the async iterator for response.content.iter_chunked
            # An async generator is an easy way to create an async iterator.
            async def chunk_generator(chunk_size):
                yield fake_image_data

            # The `content` attribute needs to have an `iter_chunked` method
            # that returns our async generator.
            mock_response.content = MagicMock()
            mock_response.content.iter_chunked = chunk_generator

        # The return value of session.get() is an async context manager.
        # We can use an AsyncMock for this, which supports `async with`.
        # The `__aenter__` of this mock will return our configured `mock_response`.
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__.return_value = mock_response
        return async_context_manager

    with patch('aiohttp.ClientSession.get', side_effect=mock_get_side_effect) as mock_session_get, \
         patch('time.sleep', return_value=None) as mock_sleep:

        # 2. Execute
        result = await discovarr_instance.reload_image_cache()

    # 3. Assertions
    assert result['success'] is True
    assert result['re_cached_count'] == 2  # Case 1 (new) and Case 6 (migrated)
    assert result['skipped_count'] == 3  # Case 2 (exists), 4 (no source), 5 (exists, wrong path)
    assert result['error_count'] == 1    # Case 3 (bad url)

    # Assert filesystem state
    assert (temp_cache_dir / "movie" / "111.jpg").exists()
    assert not (temp_cache_dir / "movie" / "333.jpg").exists()
    assert not old_cached_file_path.exists()
    assert (temp_cache_dir / "movie" / "666.jpg").exists()

    # Assert database state
    assert Media.get_by_id(media_to_recache_pk).poster_url == "movie/111.jpg"
    assert Media.get_by_id(media_cached_pk).poster_url == "movie/222.png"
    assert Media.get_by_id(media_bad_url_pk).poster_url is None
    assert Media.get_by_id(media_db_update_pk).poster_url == "movie/555.jpg"
    assert Media.get_by_id(media_old_format_pk).poster_url == "movie/666.jpg"