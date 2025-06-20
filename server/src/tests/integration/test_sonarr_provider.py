import pytest
import os
from tests.integration.base.base_live_request_provider_tests import BaseLiveRequestProviderTests
from providers.sonarr import SonarrProvider
from services.response import APIResponse

# Mark all tests in this module as 'live' to be run with `pytest -m live`
pytestmark = pytest.mark.live

class TestLiveSonarrProvider(BaseLiveRequestProviderTests):
    """
    Live integration tests for the SonarrProvider.
    
    These tests require a running Sonarr instance and are marked as 'live'.
    They use environment variables for configuration:
    - SONARR_TEST_URL: URL of the Sonarr server.
    - SONARR_TEST_API_KEY: API key for the Sonarr server.
    """

    @pytest.fixture(scope="class")
    def live_provider(self) -> SonarrProvider:
        """
        Provides a live instance of the SonarrProvider, skipping tests if not configured.
        """
        sonarr_url = os.getenv("SONARR_TEST_URL")
        sonarr_api_key = os.getenv("SONARR_TEST_API_KEY")

        if not sonarr_url or not sonarr_api_key:
            pytest.skip("SONARR_TEST_URL and SONARR_TEST_API_KEY environment variables are required for live tests.")
        
        return SonarrProvider(url=sonarr_url, api_key=sonarr_api_key)

    @pytest.fixture(scope="class")
    def tv_for_add_delete_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a TV show to be added and then deleted."""
        return 456  # The Simpsons

    @pytest.fixture(scope="class")
    def tv_for_existing_test_tmdb_id(self) -> int:
        """Provides the TMDB ID for a TV show to be added twice."""
        return 269 # One Tree Hill

    def test_add_and_delete_tv(self, live_provider: SonarrProvider, tv_for_add_delete_test_tmdb_id: int):
        """
        Tests the full lifecycle of adding a series and then deleting it.
        This ensures add_media and delete_media are working correctly.
        """
        # 1. Get necessary info for adding the series
        profiles_response = live_provider.get_quality_profiles()
        assert profiles_response.success, "Failed to get quality profiles before adding series."
        quality_profiles = profiles_response.data
        assert len(quality_profiles) > 0, "No quality profiles found in Sonarr instance."
        first_profile_id = quality_profiles[0]['id']

        default_settings = live_provider.get_default_settings()
        root_dir_path = default_settings['root_dir_path']['value']

        # 2. Add the series
        add_response = live_provider.add_media(
            tmdb_id=tv_for_add_delete_test_tmdb_id,
            quality_profile_id=first_profile_id,
            root_dir_path=root_dir_path,
            search_for_missing=False  # Don't search to make the test faster
        )

        assert isinstance(add_response, APIResponse)
        assert add_response.success, f"Failed to add series: {add_response.message} - {add_response.error}"
        
        added_series_data = add_response.data
        assert isinstance(added_series_data, dict)
        assert 'id' in added_series_data, "Response for adding a series did not contain a Sonarr ID."
        sonarr_series_id = added_series_data['id']

        # 3. Delete the series using its Sonarr ID
        delete_response = live_provider.delete_media(id=sonarr_series_id)
        
        assert isinstance(delete_response, APIResponse)
        assert delete_response.success, f"Failed to delete series: {delete_response.message}"

        # 4. Verify the series is actually gone
        verify_delete_response = live_provider._make_request("GET", f"series/{sonarr_series_id}")
        assert not verify_delete_response.success and verify_delete_response.status_code == 404, \
            f"Series was not successfully deleted from Sonarr. Status: {verify_delete_response.status_code}, Message: {verify_delete_response.message}"

    def test_add_existing_tv(self, live_provider: SonarrProvider, tv_for_existing_test_tmdb_id: int):
        """
        Tests attempting to add a series that already exists in Sonarr.
        """
        # 1. Get necessary info for adding the series
        profiles_response = live_provider.get_quality_profiles()
        assert profiles_response.success, "Failed to get quality profiles before adding series."
        quality_profiles = profiles_response.data
        assert len(quality_profiles) > 0, "No quality profiles found in Sonarr instance."
        first_profile_id = quality_profiles[0]['id']

        default_settings = live_provider.get_default_settings()
        root_dir_path = default_settings['root_dir_path']['value']

        sonarr_series_id = None
        try:
            # 2. Add the series for the first time
            live_provider.logger.info(f"Attempting to add series {tv_for_existing_test_tmdb_id} for the first time.")
            first_add_response = live_provider.add_media(
                tmdb_id=tv_for_existing_test_tmdb_id,
                quality_profile_id=first_profile_id,
                root_dir_path=root_dir_path,
                search_for_missing=False
            )
            assert first_add_response.success, f"First attempt to add series failed: {first_add_response.message} - {first_add_response.error}"
            sonarr_series_id = first_add_response.data['id']
            live_provider.logger.info(f"Successfully added series {tv_for_existing_test_tmdb_id} with Sonarr ID: {sonarr_series_id}")

            # 3. Attempt to add the same series again
            live_provider.logger.info(f"Attempting to add series {tv_for_existing_test_tmdb_id} again (should fail).")
            second_add_response = live_provider.add_media(
                tmdb_id=tv_for_existing_test_tmdb_id,
                quality_profile_id=first_profile_id,
                root_dir_path=root_dir_path,
                search_for_missing=False
            )

            # 4. Assert that the second add fails with a 400 Bad Request
            assert not second_add_response.success, f"Second attempt to add series should have failed but succeeded: {second_add_response.message}"
            assert second_add_response.status_code == 400, f"Expected 400 Bad Request for existing series, got {second_add_response.status_code}"
            assert "already been added" in str(second_add_response.error["details"]).lower(), f"Expected 'already been added' in message, got: {second_add_response.message}"
            live_provider.logger.info(f"Second add attempt correctly failed with status {second_add_response.status_code} and message: {second_add_response.message}")

        finally:
            # 5. Clean up: Delete the series if it was added
            if sonarr_series_id:
                live_provider.logger.info(f"Cleaning up: Deleting series with Sonarr ID: {sonarr_series_id}")
                delete_response = live_provider.delete_media(id=sonarr_series_id)
                assert delete_response.success, f"Failed to delete series during cleanup: {delete_response.message}"
                live_provider.logger.info(f"Successfully deleted series {sonarr_series_id} during cleanup.")
            else:
                live_provider.logger.warning(f"No Sonarr series ID obtained, skipping cleanup for TMDB ID {tv_for_existing_test_tmdb_id}.")

    def test_get_quality_profiles_structure(self, live_provider: SonarrProvider):
        """
        Tests the detailed structure of the quality profiles returned by Sonarr.
        """
        # The base test `test_get_quality_profiles` already checks for basic presence.
        # This test verifies the simplified structure returned by the provider.
        response = live_provider.get_quality_profiles()
        assert response.success, "API call to get quality profiles failed."
        
        profiles = response.data
        assert isinstance(profiles, list)
        assert len(profiles) > 0, "Expected at least one quality profile from Sonarr."

        profile = profiles[0]
        assert 'id' in profile and isinstance(profile['id'], int)
        assert 'name' in profile and isinstance(profile['name'], str)
        assert 'allowed_qualities' in profile and isinstance(profile['allowed_qualities'], list)
        assert 'is_default' in profile and isinstance(profile['is_default'], bool)

        if profile['allowed_qualities']:
            assert isinstance(profile['allowed_qualities'][0], str)