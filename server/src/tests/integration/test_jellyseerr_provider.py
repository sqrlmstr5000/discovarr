import pytest
import os
from typing import Optional
from tests.integration.base.base_live_request_provider_tests import BaseLiveRequestProviderTests
from providers.jellyseerr import JellyseerrProvider
from services.response import APIResponse

# Mark all tests in this module as 'live' to be run with `pytest -m live`
pytestmark = pytest.mark.live

class TestLiveJellyseerrProvider(BaseLiveRequestProviderTests):
    """
    Live integration tests for the JellyseerrProvider.
    
    These tests require a running Jellyseerr instance and are marked as 'live'.
    They use environment variables for configuration:
    - JELLYSEERR_TEST_URL: URL of the Jellyseerr server.
    - JELLYSEERR_TEST_API_KEY: API key for the Jellyseerr server.
    - JELLYSEERR_TEST_USER_ID: (Optional) The ID of a Jellyseerr user to make requests for.
    """

    @pytest.fixture(scope="class")
    def live_provider(self) -> JellyseerrProvider:
        """
        Provides a live instance of the JellyseerrProvider, skipping tests if not configured.
        """
        jellyseerr_url = os.getenv("JELLYSEERR_TEST_URL")
        jellyseerr_api_key = os.getenv("JELLYSEERR_TEST_API_KEY")

        if not jellyseerr_url or not jellyseerr_api_key:
            pytest.skip("JELLYSEERR_TEST_URL and JELLYSEERR_TEST_API_KEY environment variables are required for live tests.")
        
        return JellyseerrProvider(url=jellyseerr_url, api_key=jellyseerr_api_key)

    @pytest.fixture(scope="class")
    def jellyseerr_user_id(self) -> Optional[int]:
        """Provides a Jellyseerr user ID from environment variables, if available."""
        user_id_str = os.getenv("JELLYSEERR_TEST_USER_ID")
        return int(user_id_str) if user_id_str else None

    @pytest.fixture(scope="class")
    def movie_for_request_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a movie to be requested and then deleted."""
        return 299536  # Avengers: Infinity War

    @pytest.fixture(scope="class")
    def tv_for_request_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a TV show to be requested and then deleted."""
        return 60735  # The Flash

    def test_add_and_delete_movie_request(self, live_provider: JellyseerrProvider, movie_for_request_test_tmdb_id: int, jellyseerr_user_id: Optional[int]):
        """
        Tests the full lifecycle of requesting a movie and then deleting the request.
        """
        add_opts = {"user_id": jellyseerr_user_id} if jellyseerr_user_id else {}
        
        # 1. Add the movie request
        add_response = live_provider.add_media(
            tmdb_id=movie_for_request_test_tmdb_id,
            media_type='movie',
            add_options=add_opts
        )

        assert isinstance(add_response, APIResponse)
        assert add_response.success, f"Failed to add movie request: {add_response.message} - {add_response.error}"
        
        request_data = add_response.data
        assert isinstance(request_data, dict)
        assert 'id' in request_data, "Response for adding a request did not contain a request ID."
        request_id = request_data['id']

        # 2. Delete the request using its ID
        delete_response = live_provider.delete_media(request_id=request_id)
        
        assert isinstance(delete_response, APIResponse)
        assert delete_response.success, f"Failed to delete movie request: {delete_response.message}"

        # 3. Verify the request is actually gone
        verify_delete_response = live_provider._make_request("GET", f"request/{request_id}")
        assert not verify_delete_response.success and verify_delete_response.status_code == 404, \
            f"Request was not successfully deleted from Jellyseerr. Status: {verify_delete_response.status_code}, Message: {verify_delete_response.message}"

    def test_add_and_delete_tv_request(self, live_provider: JellyseerrProvider, tv_for_request_test_tmdb_id: int, jellyseerr_user_id: Optional[int]):
        """
        Tests the full lifecycle of requesting a TV show and then deleting the request.
        """
        add_opts = {"user_id": jellyseerr_user_id} if jellyseerr_user_id else {}

        # 1. Add the TV show request (all seasons)
        add_response = live_provider.add_media(
            tmdb_id=tv_for_request_test_tmdb_id,
            media_type='tv',
            add_options=add_opts
        )

        assert isinstance(add_response, APIResponse)
        assert add_response.success, f"Failed to add TV request: {add_response.message} - {add_response.error}"
        
        request_data = add_response.data
        assert isinstance(request_data, dict)
        assert 'id' in request_data, "Response for adding a request did not contain a request ID."
        request_id = request_data['id']

        # 2. Delete the request using its ID
        delete_response = live_provider.delete_media(request_id=request_id)
        
        assert isinstance(delete_response, APIResponse)
        assert delete_response.success, f"Failed to delete TV request: {delete_response.message}"

        # 3. Verify the request is actually gone
        verify_delete_response = live_provider._make_request("GET", f"request/{request_id}")
        assert not verify_delete_response.success and verify_delete_response.status_code == 404, \
            f"Request was not successfully deleted from Jellyseerr. Status: {verify_delete_response.status_code}, Message: {verify_delete_response.message}"

    def test_add_existing_movie_request(self, live_provider: JellyseerrProvider, movie_for_request_test_tmdb_id: int, jellyseerr_user_id: Optional[int]):
        """
        Tests attempting to add a movie request that already exists.
        Jellyseerr should return an error if the media is already requested and pending/approved.
        """
        add_opts = {"user_id": jellyseerr_user_id} if jellyseerr_user_id else {}
        request_id = None
        try:
            # 1. Add the movie request for the first time
            live_provider.logger.info(f"Attempting to request movie {movie_for_request_test_tmdb_id} for the first time.")
            first_add_response = live_provider.add_media(
                tmdb_id=movie_for_request_test_tmdb_id,
                media_type='movie',
                add_options=add_opts
            )
            assert first_add_response.success, f"First attempt to request movie failed: {first_add_response.message} - {first_add_response.error}"
            request_id = first_add_response.data['id']
            live_provider.logger.info(f"Successfully requested movie {movie_for_request_test_tmdb_id} with request ID: {request_id}")

            # 2. Attempt to add the same movie request again
            live_provider.logger.info(f"Attempting to request movie {movie_for_request_test_tmdb_id} again (should fail).")
            second_add_response = live_provider.add_media(
                tmdb_id=movie_for_request_test_tmdb_id,
                media_type='movie',
                add_options=add_opts
            )

            # 3. Assert that the second add fails with a 409 Conflict
            assert not second_add_response.success, f"Second attempt to request movie should have failed but succeeded: {second_add_response.message}"
            assert second_add_response.status_code == 409, f"Expected 409 Conflict for existing request, got {second_add_response.status_code}"
            assert "already exists" in str(second_add_response.error["details"]), f"Expected 'already been requested' in message, got: {second_add_response.message}"
            live_provider.logger.info(f"Second request attempt correctly failed with status {second_add_response.status_code} and message: {second_add_response.message}")

        finally:
            # 4. Clean up: Delete the request if it was created
            if request_id:
                live_provider.logger.info(f"Cleaning up: Deleting request with ID: {request_id}")
                delete_response = live_provider.delete_media(request_id=request_id)
                assert delete_response.success, f"Failed to delete request during cleanup: {delete_response.message}"
                live_provider.logger.info(f"Successfully deleted request {request_id} during cleanup.")
            else:
                live_provider.logger.warning(f"No request ID obtained, skipping cleanup for TMDB ID {movie_for_request_test_tmdb_id}.")

    def test_get_radarr_quality_profiles(self, live_provider: JellyseerrProvider):
        """
        Tests fetching Radarr quality profiles through Jellyseerr.
        """
        response = live_provider.get_radarr_quality_profiles()
        assert isinstance(response, APIResponse)
        
        # This test can only pass if a default Radarr server is configured in Jellyseerr.
        # If not, Jellyseerr will return a 404, which is a valid failure case for the test.
        if not response.success and response.status_code == 404:
            pytest.skip("No default Radarr server configured in Jellyseerr instance.")

        assert response.success, f"API call to get Radarr quality profiles via Jellyseerr failed: {response.message}"
        
        profiles = response.data
        assert isinstance(profiles, list)
        assert len(profiles) > 0, "Expected at least one Radarr quality profile from Jellyseerr."

        profile = profiles[0]
        assert 'id' in profile and isinstance(profile['id'], int)
        assert 'name' in profile and isinstance(profile['name'], str)

    def test_get_sonarr_quality_profiles(self, live_provider: JellyseerrProvider):
        """
        Tests fetching Sonarr quality profiles through Jellyseerr.
        """
        response = live_provider.get_sonarr_quality_profiles()
        assert isinstance(response, APIResponse)

        # This test can only pass if a default Sonarr server is configured in Jellyseerr.
        if not response.success and response.status_code == 404:
            pytest.skip("No default Sonarr server configured in Jellyseerr instance.")

        assert response.success, f"API call to get Sonarr quality profiles via Jellyseerr failed: {response.message}"
        
        profiles = response.data
        assert isinstance(profiles, list)
        assert len(profiles) > 0, "Expected at least one Sonarr quality profile from Jellyseerr."

        profile = profiles[0]
        assert 'id' in profile and isinstance(profile['id'], int)
        assert 'name' in profile and isinstance(profile['name'], str)