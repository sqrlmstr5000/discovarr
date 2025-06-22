import pytest
import os
from typing import Optional
from tests.integration.base.base_live_request_provider_tests import BaseLiveRequestProviderTests
from providers.overseerr import OverseerrProvider
from services.response import APIResponse

# Mark all tests in this module as 'live' to be run with `pytest -m live`
pytestmark = pytest.mark.live

class TestLiveOverseerrProvider(BaseLiveRequestProviderTests):
    """
    Live integration tests for the OverseerrProvider.
    
    These tests require a running Overseerr instance and are marked as 'live'.
    They use environment variables for configuration:
    - OVERSEERR_TEST_URL: URL of the Overseerr server.
    - OVERSEERR_TEST_API_KEY: API key for the Overseerr server.
    - OVERSEERR_TEST_USER: (Optional) The displayName of an Overseerr user to make requests for.
    """

    @pytest.fixture(scope="class")
    def live_provider(self) -> OverseerrProvider:
        """
        Provides a live instance of the OverseerrProvider, skipping tests if not configured.
        """
        overseerr_url = os.getenv("OVERSEERR_TEST_URL")
        overseerr_api_key = os.getenv("OVERSEERR_TEST_API_KEY")

        if not overseerr_url or not overseerr_api_key:
            pytest.skip("OVERSEERR_TEST_URL and OVERSEERR_TEST_API_KEY environment variables are required for live tests.")
        
        return OverseerrProvider(url=overseerr_url, api_key=overseerr_api_key)

    @pytest.fixture(scope="class")
    def overseerr_user_display_name(self) -> Optional[str]:
        """Provides an Overseerr user displayName from environment variables, if available."""
        return os.getenv("OVERSEERR_TEST_USER")

    @pytest.fixture(scope="class")
    def overseerr_user_id(self, live_provider: OverseerrProvider, overseerr_user_display_name: Optional[str]) -> Optional[int]:
        """
        Looks up and provides an Overseerr user ID based on the displayName.
        Returns None if no displayName is provided. Skips tests if the user is not found.
        """
        if not overseerr_user_display_name:
            return None

        response = live_provider.get_users(displayName=overseerr_user_display_name)
        if not response.success or not response.data:
            pytest.skip(f"Could not find user with displayName '{overseerr_user_display_name}' in Overseerr for testing.")
        
        user_data = response.data[0]
        user_id = user_data.get('id')
        return user_id

    @pytest.fixture(scope="class")
    def movie_for_request_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a movie to be requested and then deleted."""
        return 299536  # Avengers: Infinity War

    @pytest.fixture(scope="class")
    def tv_for_request_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a TV show to be requested and then deleted."""
        return 60735  # The Flash

    def test_add_and_delete_movie_request(self, live_provider: OverseerrProvider, movie_for_request_test_tmdb_id: int, overseerr_user_id: Optional[int]):
        """
        Tests the full lifecycle of requesting a movie and then deleting the request.
        """
        add_opts = {"userId": overseerr_user_id} if overseerr_user_id else {}
        
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
            f"Request was not successfully deleted from Overseerr. Status: {verify_delete_response.status_code}, Message: {verify_delete_response.message}"

    def test_add_and_delete_tv_request(self, live_provider: OverseerrProvider, tv_for_request_test_tmdb_id: int, overseerr_user_id: Optional[int]):
        """
        Tests the full lifecycle of requesting a TV show and then deleting the request.
        """
        add_opts = {"userId": overseerr_user_id} if overseerr_user_id else {}

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
            f"Request was not successfully deleted from Overseerr. Status: {verify_delete_response.status_code}, Message: {verify_delete_response.message}"

    def test_add_existing_movie_request(self, live_provider: OverseerrProvider, movie_for_request_test_tmdb_id: int, overseerr_user_id: Optional[int]):
        """
        Tests attempting to add a movie request that already exists.
        Overseerr should return an error if the media is already requested and pending/approved.
        """
        add_opts = {"userId": overseerr_user_id} if overseerr_user_id else {}
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
            # Overseerr returns a specific error code for this case
            assert "already exists" in str(second_add_response.error["details"]), f"Expected 'MEDIA_ALREADY_REQUESTED' in error details, got: {second_add_response.error['details']}"
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

    def test_get_radarr_quality_profiles(self, live_provider: OverseerrProvider):
        """
        Tests fetching Radarr quality profiles through Overseerr.
        """
        response = live_provider.get_radarr_quality_profiles()
        assert isinstance(response, APIResponse)
        
        # This test can only pass if a default Radarr server is configured in Overseerr.
        # If not, Overseerr will return a 404, which is a valid failure case for the test.
        if not response.success and response.status_code == 404:
            pytest.skip("No default Radarr server configured in Overseerr instance.")

        assert response.success, f"API call to get Radarr quality profiles via Overseerr failed: {response.message}"
        
        profiles = response.data
        assert isinstance(profiles, list)
        assert len(profiles) > 0, "Expected at least one Radarr quality profile from Overseerr."

        profile = profiles[0]
        assert 'id' in profile and isinstance(profile['id'], int)
        assert 'name' in profile and isinstance(profile['name'], str)

    def test_get_sonarr_quality_profiles(self, live_provider: OverseerrProvider):
        """
        Tests fetching Sonarr quality profiles through Overseerr.
        """
        response = live_provider.get_sonarr_quality_profiles()
        assert isinstance(response, APIResponse)

        # This test can only pass if a default Sonarr server is configured in Overseerr.
        if not response.success and response.status_code == 404:
            pytest.skip("No default Sonarr server configured in Overseerr instance.")

        assert response.success, f"API call to get Sonarr quality profiles via Overseerr failed: {response.message}"
        
        profiles = response.data
        assert isinstance(profiles, list)
        assert len(profiles) > 0, "Expected at least one Sonarr quality profile from Overseerr."

        profile = profiles[0]
        assert 'id' in profile and isinstance(profile['id'], int)
        assert 'name' in profile and isinstance(profile['name'], str)