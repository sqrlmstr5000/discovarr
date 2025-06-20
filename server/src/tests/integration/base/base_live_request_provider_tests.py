import pytest
from typing import Dict, Any
from services.response import APIResponse
from base.request_provider_base import RequestProviderBase

class BaseLiveRequestProviderTests:
    """
    Abstract base class for **live integration tests** of RequestProviderBase implementations.
    
    Subclasses must:
    1. Implement the `live_provider` fixture to return an initialized instance of the provider.
    2. Optionally override fixtures like `movie_tmdb_id` and `tv_tmdb_id` if specific media
       is needed for testing against a particular server instance.
    """

    # This fixture must be overridden by concrete test classes
    @pytest.fixture
    def live_provider(self) -> RequestProviderBase:
        """Provides a live instance of the request provider."""
        raise NotImplementedError("Subclasses must implement this fixture.")

    @pytest.fixture
    def movie_tmdb_id(self) -> int:
        """Provides a valid TMDB ID for a well-known movie."""
        return 550  # Fight Club

    @pytest.fixture
    def tv_tmdb_id(self) -> int:
        """Provides a valid TMDB ID for a well-known TV show."""
        return 1396  # Breaking Bad

    def test_provider_name(self, live_provider: RequestProviderBase):
        """Tests that the provider has a valid name."""
        assert hasattr(live_provider, 'PROVIDER_NAME')
        assert isinstance(live_provider.PROVIDER_NAME, str)
        assert len(live_provider.PROVIDER_NAME) > 0

    def test_get_quality_profiles(self, live_provider: RequestProviderBase):
        """Tests fetching quality profiles."""
        response = live_provider.get_quality_profiles()
        
        assert isinstance(response, APIResponse), "get_quality_profiles should return an APIResponse object."
        assert response.success, f"API call to get quality profiles failed: {response.message}"
        
        profiles = response.data
        assert isinstance(profiles, list), "The 'data' in the response should be a list of profiles."
        
        # Jellyseerr returns an empty list with a message, which is valid.
        if live_provider.PROVIDER_NAME == 'jellyseerr':
            assert 'manages quality profiles internally' in response.message
            return

        # For other providers, we expect profiles.
        assert len(profiles) > 0, "Expected at least one quality profile."
        
        profile = profiles[0]
        assert isinstance(profile, dict)
        assert 'id' in profile
        assert 'name' in profile

    def test_lookup_movie(self, live_provider: RequestProviderBase, movie_tmdb_id: int):
        """Tests looking up a movie by its TMDB ID."""
        # Sonarr doesn't handle movies.
        if live_provider.PROVIDER_NAME == 'sonarr':
            pytest.skip("Sonarr does not handle movies.")

        # Jellyseerr's lookup needs a media_type.
        if live_provider.PROVIDER_NAME == 'jellyseerr':
            response = live_provider.lookup_media(tmdb_id=movie_tmdb_id, media_type='movie')
        else: # Radarr
            response = live_provider.lookup_media(tmdb_id=movie_tmdb_id)
        
        assert isinstance(response, APIResponse)
        assert response.success, f"Movie lookup failed: {response.message}"
        
        movie_data = response.data
        assert isinstance(movie_data, dict)
        assert 'title' in movie_data
        # Radarr uses tmdbId, Jellyseerr uses id for tmdb_id in response
        assert movie_data.get('tmdbId') == movie_tmdb_id or movie_data.get('id') == movie_tmdb_id

    def test_lookup_tv_show(self, live_provider: RequestProviderBase, tv_tmdb_id: int):
        """Tests looking up a TV show by its TMDB ID."""
        # Radarr doesn't handle TV shows.
        if live_provider.PROVIDER_NAME == 'radarr':
            pytest.skip("Radarr does not handle TV shows.")

        # Jellyseerr's lookup needs a media_type.
        if live_provider.PROVIDER_NAME == 'jellyseerr':
            response = live_provider.lookup_media(tmdb_id=tv_tmdb_id, media_type='tv')
        else: # Sonarr
            response = live_provider.lookup_media(tmdb_id=tv_tmdb_id)

        assert isinstance(response, APIResponse)
        assert response.success, f"TV show lookup failed: {response.message}"
        
        tv_data = response.data
        assert isinstance(tv_data, dict)
        #assert 'title' in tv_data
        # Sonarr uses tmdbId, Jellyseerr uses id for tmdb_id in response
        assert tv_data.get('tmdbId') == tv_tmdb_id or tv_data.get('id') == tv_tmdb_id