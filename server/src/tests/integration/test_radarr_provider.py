import pytest
import os
from tests.integration.base.base_live_request_provider_tests import BaseLiveRequestProviderTests
from providers.radarr import RadarrProvider
from services.response import APIResponse

# Mark all tests in this module as 'live' to be run with `pytest -m live`
pytestmark = pytest.mark.live

class TestLiveRadarrProvider(BaseLiveRequestProviderTests):
    """
    Live integration tests for the RadarrProvider.
    
    These tests require a running Radarr instance and are marked as 'live'.
    They use environment variables for configuration:
    - RADARR_TEST_URL: URL of the Radarr server.
    - RADARR_TEST_API_KEY: API key for the Radarr server.
    """

    @pytest.fixture(scope="class")
    def live_provider(self) -> RadarrProvider:
        """
        Provides a live instance of the RadarrProvider, skipping tests if not configured.
        """
        radarr_url = os.getenv("RADARR_TEST_URL")
        radarr_api_key = os.getenv("RADARR_TEST_API_KEY")

        if not radarr_url or not radarr_api_key:
            pytest.skip("RADARR_TEST_URL and RADARR_TEST_API_KEY environment variables are required for live tests.")
        
        return RadarrProvider(url=radarr_url, api_key=radarr_api_key)

    @pytest.fixture(scope="class")
    def movie_for_add_delete_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a movie to be added and then deleted."""
        return 597  # Titanic

    @pytest.fixture(scope="class")
    def movie_for_existing_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a movie to be added twice."""
        return 8587 # The Lion King

    def test_add_and_delete_movie(self, live_provider: RadarrProvider, movie_for_add_delete_test_tmdb_id: int):
        """
        Tests the full lifecycle of adding a movie and then deleting it.
        This ensures add_media and delete_media are working correctly.
        """
        # 1. Get necessary info for adding the movie
        profiles_response = live_provider.get_quality_profiles()
        assert profiles_response.success, "Failed to get quality profiles before adding movie."
        quality_profiles = profiles_response.data
        assert len(quality_profiles) > 0, "No quality profiles found in Radarr instance."
        first_profile_id = quality_profiles[0]['id']

        default_settings = live_provider.get_default_settings()
        root_dir_path = default_settings['root_dir_path']['value']

        # 2. Add the movie
        add_response = live_provider.add_media(
            tmdb_id=movie_for_add_delete_test_tmdb_id,
            quality_profile_id=first_profile_id,
            root_dir_path=root_dir_path,
            search_for_movie=False  # Don't search to make the test faster and less resource-intensive
        )

        assert isinstance(add_response, APIResponse)
        assert add_response.success, f"Failed to add movie: {add_response.message} - {add_response.error}"
        
        added_movie_data = add_response.data
        assert isinstance(added_movie_data, dict)
        assert 'id' in added_movie_data, "Response for adding a movie did not contain a Radarr ID."
        radarr_movie_id = added_movie_data['id']

        # 3. Delete the movie using its Radarr ID
        delete_response = live_provider.delete_media(id=radarr_movie_id)
        
        assert isinstance(delete_response, APIResponse)
        assert delete_response.success, f"Failed to delete movie: {delete_response.message}"

        # 4. Verify the movie is actually gone
        verify_delete_response = live_provider._make_request("GET", f"movie/{radarr_movie_id}")
        assert not verify_delete_response.success and verify_delete_response.status_code == 404, \
            f"Movie was not successfully deleted from Radarr. Status: {verify_delete_response.status_code}, Message: {verify_delete_response.message}"

    def test_add_existing_movie(self, live_provider: RadarrProvider, movie_for_existing_test_tmdb_id: int):
        """
        Tests attempting to add a movie that already exists in Radarr.
        """
        # 1. Get necessary info for adding the movie
        profiles_response = live_provider.get_quality_profiles()
        assert profiles_response.success, "Failed to get quality profiles before adding movie."
        quality_profiles = profiles_response.data
        assert len(quality_profiles) > 0, "No quality profiles found in Radarr instance."
        first_profile_id = quality_profiles[0]['id']

        default_settings = live_provider.get_default_settings()
        root_dir_path = default_settings['root_dir_path']['value']

        radarr_movie_id = None
        try:
            # 2. Add the movie for the first time
            live_provider.logger.info(f"Attempting to add movie {movie_for_existing_test_tmdb_id} for the first time.")
            first_add_response = live_provider.add_media(
                tmdb_id=movie_for_existing_test_tmdb_id,
                quality_profile_id=first_profile_id,
                root_dir_path=root_dir_path,
                search_for_movie=False
            )
            assert first_add_response.success, f"First attempt to add movie failed: {first_add_response.message} - {first_add_response.error}"
            radarr_movie_id = first_add_response.data['id']
            live_provider.logger.info(f"Successfully added movie {movie_for_existing_test_tmdb_id} with Radarr ID: {radarr_movie_id}")

            # 3. Attempt to add the same movie again
            live_provider.logger.info(f"Attempting to add movie {movie_for_existing_test_tmdb_id} again (should fail).")
            second_add_response = live_provider.add_media(
                tmdb_id=movie_for_existing_test_tmdb_id,
                quality_profile_id=first_profile_id,
                root_dir_path=root_dir_path,
                search_for_movie=False
            )

            # 4. Assert that the second add fails with a 409 Conflict
            assert not second_add_response.success, f"Second attempt to add movie should have failed but succeeded: {second_add_response.message}"
            assert second_add_response.status_code == 400, f"Expected 409 Conflict for existing movie, got {second_add_response.status_code}"
            assert "already been added" in str(second_add_response.error["details"]), f"Expected 'already exists' in message, got: {second_add_response.message}"
            live_provider.logger.info(f"Second add attempt correctly failed with status {second_add_response.status_code} and message: {second_add_response.message}")

        finally:
            # 5. Clean up: Delete the movie if it was added
            if radarr_movie_id:
                live_provider.logger.info(f"Cleaning up: Deleting movie with Radarr ID: {radarr_movie_id}")
                delete_response = live_provider.delete_media(id=radarr_movie_id)
                assert delete_response.success, f"Failed to delete movie during cleanup: {delete_response.message}"
                live_provider.logger.info(f"Successfully deleted movie {radarr_movie_id} during cleanup.")
            else:
                live_provider.logger.warning(f"No Radarr movie ID obtained, skipping cleanup for TMDB ID {movie_for_existing_test_tmdb_id}.")

    def test_get_quality_profiles_structure(self, live_provider: RadarrProvider):
        """
        Tests the detailed structure of the quality profiles returned by Radarr.
        """
        # The base test `test_get_quality_profiles` already checks for basic presence.
        # This test verifies the simplified structure returned by the provider.
        response = live_provider.get_quality_profiles()
        assert response.success, "API call to get quality profiles failed."
        
        profiles = response.data
        assert isinstance(profiles, list)
        assert len(profiles) > 0, "Expected at least one quality profile from Radarr."

        profile = profiles[0]
        assert 'id' in profile and isinstance(profile['id'], int)
        assert 'name' in profile and isinstance(profile['name'], str)
        assert 'allowed_qualities' in profile and isinstance(profile['allowed_qualities'], list)
        assert 'is_default' in profile and isinstance(profile['is_default'], bool)

        if profile['allowed_qualities']:
            assert isinstance(profile['allowed_qualities'][0], str)