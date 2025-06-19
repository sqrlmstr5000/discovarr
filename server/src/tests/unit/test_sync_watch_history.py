import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY # Import ANY
from services.models import LibraryUser, ItemsFiltered, Media # Assuming these are Pydantic models or similar
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
        # Mock settings to disable all providers
        test_settings = {
            ("plex", "enabled"): False,
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
        }        
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration() # Reload to apply mocked settings

        dv.db.get_watch_history_count_for_source = MagicMock()
        # Patch _sync_watch_history_to_db to ensure it's not called
        dv.db.get_media_count_for_provider = MagicMock()
        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            assert result == {}
            # After reload_configuration with disabled providers, dv.plex etc. will be None.
            # The fixture ensures they are mocks initially.
            # The sync_watch_history method checks for enabled status before calling.
            # So, we don't assert on dv.plex.get_users directly if dv.plex is None.
            # The critical part is that no error occurs and _sync_watch_history_to_db isn't called.
            dv.db.get_media_count_for_provider.assert_not_called()
            mock_sync_to_db.assert_not_called()

    async def test_one_provider_enabled_no_users(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()
        dv.plex.get_users.return_value = [] # dv.plex is a MagicMock due to class patch
        dv.db.get_media_count_for_provider = MagicMock()

        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            assert result == {} # No users, so no data in result
            dv.plex.get_users.assert_called_once()
            dv.plex.get_recently_watched.assert_not_called()
            # get_media_count_for_provider is called *after* users are fetched and iterated
            dv.db.get_media_count_for_provider.assert_not_called()
            mock_sync_to_db.assert_not_called()

    async def test_one_provider_user_found_no_recent_items(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("app", "recent_limit"): 5, # Set recent_limit via settings
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[]) # No recent items
        dv.db.get_media_count_for_provider = MagicMock(return_value=0) # No existing history

        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock) as mock_sync_to_db:
            result = await dv.sync_watch_history()
            
            # User key exists because get_users returned a user, but recent_titles is empty
            assert result == {'Plex User 1': {'id': 'plex_user1_id', 'recent_titles': []}}
            dv.plex.get_users.assert_called_once()
            dv.db.get_media_count_for_provider.assert_called_once_with("plex")
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user1.id, limit=None) # limit=None because history_count=0, as per logic
            mock_sync_to_db.assert_not_called() # _sync_watch_history_to_db is not called if recently_watched_items is empty

    async def test_one_provider_user_found_with_recent_items_no_db_history(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("app", "recent_limit"): 10,
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a]) # Returns List[ItemsFiltered]
        dv.db.get_media_count_for_provider = MagicMock(return_value=0) # No existing history

        # Mock _sync_watch_history_to_db to verify its call and control its return
        # _sync_watch_history_to_db returns List[ItemsFiltered]
        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[item_movie_a]) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            expected_result = {'Plex User 1': {'id': 'plex_user1_id', 'recent_titles': ['Movie A']}}
            assert result == expected_result
            dv.plex.get_users.assert_called_once()
            dv.db.get_media_count_for_provider.assert_called_once_with("plex")
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user1.id, limit=None) # limit=None because history_count=0
            mock_sync_to_db.assert_called_once_with(
                user_name=plex_user1.name,
                user_id=plex_user1.id,
                recently_watched_items=[item_movie_a],
                source="plex"
            )

    async def test_one_provider_user_found_with_recent_items_with_db_history(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("app", "recent_limit"): 10,
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a, item_tv_b]) # Returns List[ItemsFiltered]
        dv.db.get_media_count_for_provider = MagicMock(return_value=10) # Existing history

        # _sync_watch_history_to_db returns List[ItemsFiltered]
        with patch.object(dv, '_sync_watch_history_to_db', new_callable=AsyncMock, return_value=[item_movie_a, item_tv_b]) as mock_sync_to_db:
            result = await dv.sync_watch_history()

            expected_result = {'Plex User 1': {'id': 'plex_user1_id', 'recent_titles': sorted(['Movie A', 'TV Show B'])}}
            # The method sorts titles at the end, so we assert against sorted list
            assert result == expected_result

            dv.plex.get_users.assert_called_once()
            dv.db.get_media_count_for_provider.assert_called_once_with("plex")
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user1.id, limit=dv.recent_limit)
            mock_sync_to_db.assert_called_once_with(
                user_name=plex_user1.name,
                user_id=plex_user1.id,
                recently_watched_items=[item_movie_a, item_tv_b], # Pass the ItemsFiltered objects
                source="plex"
            )

    async def test_sync_to_db_with_poster_url_caches_image(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("tmdb", "api_key"): "fake_tmdb_key",
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a]) # Has poster_url
        dv.db.get_media_count_for_provider = MagicMock(return_value=0)
                # Mock create_media to return a specific PK, which is then passed to add_watch_history
        mock_media_pk = 999
        dv.db.create_media = MagicMock(return_value=mock_media_pk)
        dv.db.add_watch_history = MagicMock() 

        # Create a mock Media instance that Media.get_by_id will return
        mock_media_instance_after_creation = MagicMock(spec=Media)
        mock_media_instance_after_creation.id = mock_media_pk
        mock_media_instance_after_creation.title = item_movie_a.name
        # These attributes are set during media_data_for_creation in _sync_watch_history_to_db
        mock_media_instance_after_creation.watched = True 
        mock_media_instance_after_creation.watch_count = 1
        mock_media_instance_after_creation.favorite = item_movie_a.is_favorite # Match item's favorite status

        # Mock _cache_image_if_needed which calls image_cache.save_image_from_url
        # We want to assert _cache_image_if_needed is called correctly and db.add_watch_history gets the result
        # Patch Media.get_by_id where it's defined and used by discovarr.py
        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock, return_value="cache/plex_tmdb1.jpg") as mock_cache_needed, \
             patch('services.models.Media.get_by_id', return_value=mock_media_instance_after_creation) as mock_media_get_by_id_call:
            
            await dv.sync_watch_history()

            mock_cache_needed.assert_called_once_with(item_movie_a.poster_url, "plex", item_movie_a.id)
            mock_media_get_by_id_call.assert_called_once_with(mock_media_pk)
            dv.db.add_watch_history.assert_called_once_with(
                media_id=mock_media_pk,
                watched_by=plex_user1.name,
                last_played_date_iso=item_movie_a.last_played_date
            )


    async def test_sync_to_db_no_poster_url_tmdb_lookup_success_caches_image(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("tmdb", "api_key"): "fake_tmdb_key", # Ensure TMDB is considered configured
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()
        
        # Ensure dv.tmdb is a mock that can be configured for this test
        dv.tmdb = MagicMock() 

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_c_no_poster]) # No poster_url
        dv.db.get_media_count_for_provider = MagicMock(return_value=0)
        dv.db.add_watch_history = AsyncMock()
        mock_media_pk = 123
        dv.db.create_media = MagicMock(return_value=mock_media_pk) # Mock create_media to return a PK

        # Create a mock Media instance that Media.get_by_id will return
        mock_media_instance_after_creation = MagicMock(spec=Media)
        mock_media_instance_after_creation.id = mock_media_pk
        mock_media_instance_after_creation.title = item_movie_c_no_poster.name
        mock_media_instance_after_creation.watched = True 
        mock_media_instance_after_creation.watch_count = 1
        mock_media_instance_after_creation.favorite = item_movie_c_no_poster.is_favorite

        dv.tmdb.get_media_detail = MagicMock(return_value={'poster_path': '/tmdb_poster.jpg'})
        tmdb_poster_full_url = "https://image.tmdb.org/t/p/w500/tmdb_poster.jpg"

        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock, return_value="cache/plex_tmdb3.jpg") as mock_cache_needed, \
             patch('services.models.Media.get_by_id', return_value=mock_media_instance_after_creation) as mock_media_get_by_id_call:
            await dv.sync_watch_history()

            dv.tmdb.get_media_detail.assert_called_once_with(tmdb_id=item_movie_c_no_poster.id, media_type=item_movie_c_no_poster.type)
            mock_cache_needed.assert_called_once_with(tmdb_poster_full_url, "plex", item_movie_c_no_poster.id) # item_movie_c_no_poster.id is tmdb_id
            mock_media_get_by_id_call.assert_called_once_with(mock_media_pk)
            dv.db.add_watch_history.assert_called_once_with(
                media_id=mock_media_pk, # Assert it's called with the PK from create_media
                watched_by=plex_user1.name,
                last_played_date_iso=item_movie_c_no_poster.last_played_date
            )
            # Verify that the save method on the mock_media_instance_after_creation was NOT called
            # because newly_created_media is True in this path.
            mock_media_instance_after_creation.save.assert_not_called()

    async def test_sync_to_db_no_poster_url_tmdb_lookup_fail(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("tmdb", "api_key"): "fake_tmdb_key",
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()
        dv.tmdb = MagicMock()

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_c_no_poster]) # No poster_url
        dv.db.get_media_count_for_provider = MagicMock(return_value=0)
        dv.db.add_watch_history = AsyncMock()
        mock_media_pk = 456
        dv.db.create_media = MagicMock(return_value=mock_media_pk) # Mock create_media

        # Create a mock Media instance that Media.get_by_id will return
        mock_media_instance_after_creation = MagicMock(spec=Media)
        mock_media_instance_after_creation.id = mock_media_pk
        mock_media_instance_after_creation.title = item_movie_c_no_poster.name
        mock_media_instance_after_creation.watched = True
        mock_media_instance_after_creation.watch_count = 1
        mock_media_instance_after_creation.favorite = item_movie_c_no_poster.is_favorite

        dv.tmdb.get_media_detail = MagicMock(return_value=None) # TMDB lookup fails

        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock) as mock_cache_needed, \
             patch('services.models.Media.get_by_id', return_value=mock_media_instance_after_creation) as mock_media_get_by_id_call:
            await dv.sync_watch_history()

            dv.tmdb.get_media_detail.assert_called_once_with(tmdb_id=item_movie_c_no_poster.id, media_type=item_movie_c_no_poster.type) # item_movie_c_no_poster.id is tmdb_id
            # _cache_image_if_needed should not be called if url_to_cache remains None
            mock_cache_needed.assert_not_called()
            mock_media_get_by_id_call.assert_called_once_with(mock_media_pk)
            dv.db.add_watch_history.assert_called_once_with(
                media_id=mock_media_pk, # Assert it's called with the PK from create_media
                watched_by=plex_user1.name,
                last_played_date_iso=item_movie_c_no_poster.last_played_date
            )
            # Verify that the save method on the mock_media_instance_after_creation was NOT called
            # because newly_created_media is True in this path.
            mock_media_instance_after_creation.save.assert_not_called()

    async def test_sync_to_db_cache_image_fails_uses_original_url(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "enabled"): False,
            ("trakt", "enabled"): False,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()

        dv.plex.get_users = MagicMock(return_value=[plex_user1])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_movie_a]) # Has poster_url
        dv.db.get_media_count_for_provider = MagicMock(return_value=0)
        dv.db.add_watch_history = AsyncMock()
        mock_media_pk = 789
        dv.db.create_media = MagicMock(return_value=mock_media_pk) # Mock 
        
        # Create a mock Media instance that Media.get_by_id will return
        mock_media_instance_after_creation = MagicMock(spec=Media)
        mock_media_instance_after_creation.id = mock_media_pk
        mock_media_instance_after_creation.title = item_movie_a.name
        mock_media_instance_after_creation.watched = True
        mock_media_instance_after_creation.watch_count = 1
        mock_media_instance_after_creation.favorite = item_movie_a.is_favorite

        # Mock _cache_image_if_needed to return the original URL (simulating cache failure but fallback)
        with patch.object(dv, '_cache_image_if_needed', new_callable=AsyncMock, return_value=item_movie_a.poster_url) as mock_cache_needed, \
             patch('services.models.Media.get_by_id', return_value=mock_media_instance_after_creation) as mock_media_get_by_id_call:
            await dv.sync_watch_history()

            mock_cache_needed.assert_called_once_with(item_movie_a.poster_url, "plex", item_movie_a.id) # item_movie_a.id is tmdb_id
            mock_media_get_by_id_call.assert_called_once_with(mock_media_pk)
            dv.db.add_watch_history.assert_called_once_with(
                media_id=789, # PK from create_media
                watched_by=plex_user1.name,
                last_played_date_iso=item_movie_a.last_played_date
            )
            # Verify that the save method on the mock_media_instance_after_creation was NOT called
            # because newly_created_media is True in this path.
            mock_media_instance_after_creation.save.assert_not_called()
    
    async def test_multiple_providers_data_aggregation(self, mocked_discovarr_instance: Discovarr):
        dv = mocked_discovarr_instance
        test_settings = {
            ("plex", "enabled"): True,
            ("plex", "enable_history"): True,
            ("plex", "url"): "http://mockplex.test", # Add URL
            ("plex", "api_key"): "mockplexkey.test", # Add API Key
            ("jellyfin", "url"): "http://mockjellyfin.test", # Add URL
            ("jellyfin", "api_key"): "mockjellyfinkey.test", # Add API Key
            ("jellyfin", "enabled"): True,
            ("jellyfin", "enable_history"): True,
            ("radarr", "url"): "http://mockradarr:7878", # Include Radarr settings
            ("sonarr", "url"): "http://mocksonarr:7878", # Include Sonarr settings
            ("radarr", "root_dir_path"): "/mock/radarr/root", # Include Radarr settings
            ("radarr", "api_key"): "mock_radarr_key", # Include Radarr settings
            ("sonarr", "api_key"): "mock_sonarr_key",
            ("sonarr", "root_dir_path"): "/mock/sonarr/root",
            ("trakt", "enabled"): False,
            ("app", "recent_limit"): 10, # Default if not overridden
        }
        dv.settings.get.side_effect = lambda group, key, default=None: test_settings.get((group, key), default)
        dv.reload_configuration()

        # Mock Media.get_or_none to simulate media already existing or not
        patcher = patch('discovarr.Media.get_or_none', return_value=None) # Simulate media not existing, so it gets created
        mock_media_get_or_none = patcher.start()

        jellyfin_user_shared = LibraryUser(id='jf_user_shared_id', name='Shared User', source_provider='jellyfin')
        plex_user_shared = LibraryUser(id='plex_user_shared_id', name='Shared User', source_provider='plex') # Same name

        item_jf_x = ItemsFiltered(name='Movie X JF', id='tmdbX', type='movie', last_played_date='dateX', poster_url='urlX')
        item_plex_y = ItemsFiltered(name='Movie Y Plex', id='tmdbY', type='movie', last_played_date='dateY', poster_url='urlY')
        
        dv.plex.get_users = MagicMock(return_value=[plex_user_shared])
        dv.plex.get_recently_watched = MagicMock(return_value=[item_plex_y])
        
        dv.jellyfin.get_users = MagicMock(return_value=[jellyfin_user_shared])
        dv.jellyfin.get_recently_watched = MagicMock(return_value=[item_jf_x])

        dv.db.get_media_count_for_provider = MagicMock(return_value=0) # Limit=None for both

        # Let _sync_watch_history_to_db return the items passed to it
        async def mock_sync_side_effect(user_name, user_id, recently_watched_items, source): # recently_watched_items is List[ItemsFiltered]
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
            
            dv.db.get_media_count_for_provider.assert_any_call("plex")
            dv.db.get_media_count_for_provider.assert_any_call("jellyfin")
            assert dv.db.get_media_count_for_provider.call_count == 2
            
            dv.plex.get_recently_watched.assert_called_once_with(user_id=plex_user_shared.id, limit=None) # limit=None because history_count=0
            dv.jellyfin.get_recently_watched.assert_called_once_with(user_id=jellyfin_user_shared.id, limit=None)
            
            mock_sync_db.assert_any_call(user_name='Shared User', user_id=plex_user_shared.id, recently_watched_items=[item_plex_y], source='plex')
            mock_sync_db.assert_any_call(user_name='Shared User', user_id=jellyfin_user_shared.id, recently_watched_items=[item_jf_x], source='jellyfin')
            assert mock_sync_db.call_count == 2
        
        patcher.stop() # Stop the patch for Media.get_or_none
