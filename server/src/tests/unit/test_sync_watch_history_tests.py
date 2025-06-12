import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.models import LibraryUser, ItemsFiltered # Assuming these are Pydantic models or similar
from discovarr import Discovarr # Import Discovarr for type hinting
from tests.unit.base.base_discovarr_tests import mocked_discovarr_instance # Import the new base fixture

# Common test data
plex_user1 = LibraryUser(id='plex_user1_id', name='Plex User 1', source_provider='plex', thumb='url1')
jellyfin_user1 = LibraryUser(id='jf_user1_id', name='JF User 1', source_provider='jellyfin', thumb='url2')

item_movie_a = ItemsFiltered(name='Movie A', id='tmdb1', type='movie', last_played_date='2023-01-01T00:00:00Z', poster_url='http://example.com/posterA.jpg')
item_tv_b = ItemsFiltered(name='TV Show B', id='tmdb2', type='tv', last_played_date='2023-01-02T00:00:00Z', poster_url='http://example.com/posterB.jpg')
item_movie_c_no_poster = ItemsFiltered(name='Movie C', id='tmdb3', type='movie', last_played_date='2023-01-03T00:00:00Z', poster_url=None)

@pytest.mark.asyncio
class TestSyncWatchHistory:

    async def test_no_providers_enabled(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        # Ensure providers are disabled
        dv.plex_enabled = False
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False

        # Mock provider methods to ensure they are not called
        dv.plex.get_users = MagicMock()
        dv.jellyfin.get_users = MagicMock()
        dv.trakt.get_users = MagicMock()

        dv.db.get_watch_history_count_for_source = MagicMock()
        # Patch _sync_watch_history_to_db to ensure it's not called
        # dv._sync_watch_history_to_db is an internal async method, so we patch it on the instance
        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            assert result == {}
            dv.plex.get_users.assert_not_called()
            dv.jellyfin.get_users.assert_not_called()
            dv.trakt.get_users.assert_not_called()
            dv.db.get_watch_history_count_for_source.assert_not_called()
            mock_sync_to_db.assert_not_called()

    async def test_one_provider_enabled_no_users(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False

        dv.plex.get_users = MagicMock(return_value=[]) # No users
        dv.plex.get_recently_watched = MagicMock()
        dv.db.get_watch_history_count_for_source = MagicMock()

        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            assert result == {} # No users, so no data in result
            dv.plex.get_users.assert_called_once()
            dv.plex.get_recently_watched.assert_not_called()
            # get_watch_history_count_for_source is called *after* users are fetched and iterated
            dv.db.get_watch_history_count_for_source.assert_not_called()
            mock_sync_to_db.assert_not_called()

    async def test_one_provider_user_found_no_recent_items(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False
        dv.recent_limit = 5 # Set a known recent_limit for the test

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[]) # No recent items
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0) # No existing history

        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock) as mock_sync_to_db:
            result = await dv.sync_watch_history()
            
            # User key exists because get_users returned a user, but recent_titles is empty
            assert result == {'Plex User 1': {'id': 'plex_user1_id', 'recent_titles': []}}
            dv.plex.get_users.assert_called_once()
            dv.db.get_watch_history_count_for_source.assert_called_once_with("plex")
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user1.id, limit=None) # limit=None because history_count=0
            mock_sync_to_db.assert_not_called() # Not called if no recent items

    async def test_one_provider_user_found_with_recent_items_no_db_history(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False
        dv.recent_limit = 10 # Default from settings if not overridden

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a])
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0) # No existing history

        # Mock _sync_watch_history_to_db to verify its call and control its return
        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[item_movie_a]) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            expected_result = {'Plex User 1': {'id': 'plex_user1_id', 'recent_titles': ['Movie A']}}
            assert result == expected_result
            dv.plex.get_users.assert_called_once()
            dv.db.get_watch_history_count_for_source.assert_called_once_with("plex")
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user1.id, limit=None)
            mock_sync_to_db.assert_called_once_with(
                user_name=plex_user1.name,
                user_id=plex_user1.id,
                recently_watched_items=[item_movie_a],
                source="plex"
            )

    async def test_one_provider_user_found_with_recent_items_with_db_history(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False
        dv.recent_limit = 10 # Explicitly set to test this path

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a, item_tv_b])
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=10) # Existing history

        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[item_movie_a, item_tv_b]) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            expected_result = {'Plex User 1': {'id': 'plex_user1_id', 'recent_titles': sorted(['Movie A', 'TV Show B'])}}
            # The method sorts titles at the end, so we assert against sorted list
            assert result == expected_result

            dv.plex.get_users.assert_called_once()
            dv.db.get_watch_history_count_for_source.assert_called_once_with("plex")
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user1.id, limit=dv.recent_limit)
            mock_sync_to_db.assert_called_once_with(
                user_name=plex_user1.name,
                user_id=plex_user1.id,
                recently_watched_items=[item_movie_a, item_tv_b],
                source="plex"
            )

    async def test_sync_to_db_with_poster_url_caches_image(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a]) # Has poster_url
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0)
        dv.db.add_watch_history = MagicMock()

        # Mock _cache_image_if_needed which calls image_cache.save_image_from_url
        # We want to assert _cache_image_if_needed is called correctly and db.add_watch_history gets the result
        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock, return_value="cache/plex_tmdb1.jpg") as mock_cache_needed:
            await dv.sync_watch_history()

            mock_cache_needed.assert_called_once_with(item_movie_a.poster_url, "plex", item_movie_a.id)
            dv.db.add_watch_history.assert_called_once_with(
                title=item_movie_a.name,
                id=item_movie_a.id,
                media_type=item_movie_a.type,
                watched_by=plex_user1.name,
                last_played_date=item_movie_a.last_played_date,
                poster_url="cache/plex_tmdb1.jpg", # Cached path
                poster_url_source=item_movie_a.poster_url, # Original path
                source="plex"
            )

    async def test_sync_to_db_no_poster_url_tmdb_lookup_success_caches_image(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_c_no_poster]) # No poster_url
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0)
        dv.db.add_watch_history = MagicMock()

        # Mock TMDB
        dv.tmdb = MagicMock() # Ensure tmdb is mocked if not already by fixture
        dv.tmdb.get_media_detail = MagicMock(return_value={'poster_path': '/tmdb_poster.jpg'})
        tmdb_poster_full_url = "https://image.tmdb.org/t/p/w500/tmdb_poster.jpg"

        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock, return_value="cache/plex_tmdb3.jpg") as mock_cache_needed:
            await dv.sync_watch_history()

            dv.tmdb.get_media_detail.assert_called_once_with(tmdb_id=item_movie_c_no_poster.id, media_type=item_movie_c_no_poster.type)
            mock_cache_needed.assert_called_once_with(tmdb_poster_full_url, "plex", item_movie_c_no_poster.id)
            dv.db.add_watch_history.assert_called_once_with(
                title=item_movie_c_no_poster.name,
                id=item_movie_c_no_poster.id,
                media_type=item_movie_c_no_poster.type,
                watched_by=plex_user1.name,
                last_played_date=item_movie_c_no_poster.last_played_date,
                poster_url="cache/plex_tmdb3.jpg",
                poster_url_source=tmdb_poster_full_url,
                source="plex"
            )

    async def test_sync_to_db_no_poster_url_tmdb_lookup_fail(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_c_no_poster]) # No poster_url
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0)
        dv.db.add_watch_history = MagicMock()

        dv.tmdb = MagicMock()
        dv.tmdb.get_media_detail = MagicMock(return_value=None) # TMDB lookup fails

        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock) as mock_cache_needed:
            await dv.sync_watch_history()

            dv.tmdb.get_media_detail.assert_called_once_with(tmdb_id=item_movie_c_no_poster.id, media_type=item_movie_c_no_poster.type)
            # _cache_image_if_needed should not be called if url_to_cache remains None
            mock_cache_needed.assert_not_called()
            dv.db.add_watch_history.assert_called_once_with(
                title=item_movie_c_no_poster.name,
                id=item_movie_c_no_poster.id,
                media_type=item_movie_c_no_poster.type,
                watched_by=plex_user1.name,
                last_played_date=item_movie_c_no_poster.last_played_date,
                poster_url=None, # No poster URL found or cached
                poster_url_source=None, # No source URL
                source="plex"
            )

    async def test_sync_to_db_cache_image_fails_uses_original_url(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Explicitly enable history sync
        dv.jellyfin_enabled = False
        dv.trakt_enabled = False

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a]) # Has poster_url
        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0)
        dv.db.add_watch_history = MagicMock()

        # Mock _cache_image_if_needed to return the original URL (simulating cache failure but fallback)
        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock, return_value=item_movie_a.poster_url) as mock_cache_needed:
            await dv.sync_watch_history()

            mock_cache_needed.assert_called_once_with(item_movie_a.poster_url, "plex", item_movie_a.id)
            dv.db.add_watch_history.assert_called_once_with(
                title=item_movie_a.name,
                id=item_movie_a.id,
                media_type=item_movie_a.type,
                watched_by=plex_user1.name,
                last_played_date=item_movie_a.last_played_date,
                poster_url=item_movie_a.poster_url, # Falls back to original URL
                poster_url_source=item_movie_a.poster_url,
                source="plex"
            )
    
    async def test_multiple_providers_data_aggregation(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        dv.plex_enabled = True
        dv.plex_enable_history = True # Ensure Plex history sync is enabled for this test
        dv.jellyfin_enabled = True
        dv.jellyfin_enable_history = True # Ensure Jellyfin history sync is enabled for this test
        dv.trakt_enabled = False # Keep it simple for now
        # dv.recent_limit will be 10 (default)

        jellyfin_user_shared = LibraryUser(id='jf_user_shared_id', name='Shared User', source_provider='jellyfin')
        plex_user_shared = LibraryUser(id='plex_user_shared_id', name='Shared User', source_provider='plex') # Same name

        item_jf_x = ItemsFiltered(name='Movie X JF', id='tmdbX', type='movie', last_played_date='dateX', poster_url='urlX')
        item_plex_y = ItemsFiltered(name='Movie Y Plex', id='tmdbY', type='movie', last_played_date='dateY', poster_url='urlY')
        
        dv.plex.get_users = MagicMock(return_value=[plex_user_shared])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_plex_y])
        
        dv.jellyfin.get_users = MagicMock(return_value=[jellyfin_user_shared])
        dv.jellyfin.get_recently_watched = MagicMock(return_value=[item_jf_x])

        dv.db.get_watch_history_count_for_source = MagicMock(return_value=0) # Limit=None for both

        # Let _sync_watch_history_to_db return the items passed to it
        async def mock_sync_side_effect(user_name, user_id, recently_watched_items, source):
            return recently_watched_items

        with patch.object(dv, '_sync_watch_history_to_db', side_effect=mock_sync_side_effect) as mock_sync_db:
            result = await dv.sync_watch_history()
            
            #assert 'Shared User' in result
            # Titles should be combined, de-duplicated, and sorted by the main method
            expected_titles_for_shared_user = sorted(list(set(['Movie X JF', 'Movie Y Plex'])))
            assert result['Shared User']['recent_titles'] == expected_titles_for_shared_user
            
            # Verify calls
            dv.plex.get_users.assert_called_once()
            dv.jellyfin.get_users.assert_called_once()
            
            dv.db.get_watch_history_count_for_source.assert_any_call("plex")
            dv.db.get_watch_history_count_for_source.assert_any_call("jellyfin")
            assert dv.db.get_watch_history_count_for_source.call_count == 2
            
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user_shared.id, limit=None)
            dv.jellyfin.get_recently_watched.assert_called_once_with(user_id=jellyfin_user_shared.id, limit=None)
            
            mock_sync_db.assert_any_call(user_name='Shared User', user_id=plex_user_shared.id, recently_watched_items=[item_plex_y], source='plex')
            mock_sync_db.assert_any_call(user_name='Shared User', user_id=jellyfin_user_shared.id, recently_watched_items=[item_jf_x], source='jellyfin')
            assert mock_sync_db.call_count == 2
