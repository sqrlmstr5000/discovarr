import json
import logging
from typing import Optional, Dict, Any, List
from base.request_provider_base import RequestProviderBase
from services.response import APIResponse
from services.models import SettingType # Import SettingType

class SonarrProvider(RequestProviderBase):
    PROVIDER_NAME = "sonarr"

    def __init__(self, url: str, api_key: str):
        """Initialize Sonarr client.
        
        Args:
            url (str): The URL of your Sonarr server (e.g., "http://your-sonarr-server:8989")
            api_key (str): Your Sonarr API key
        """
        super().__init__(url=url, api_key=api_key, api_key_header_name="X-Api-Key", api_base_path="api/v3")
        self.logger = logging.getLogger(__name__)
        # self.url, self.api_key, and self.headers are now managed by the Api base class

    def lookup_media(self, tmdb_id: str) -> APIResponse:
        """Look up series details using IMDB ID.
        
        Args:
            tmdb_id (str): The IMDB ID of the series
            
        Returns:
            APIResponse: An APIResponse object. If successful, `data` contains series details.
        """
        lookup_params = {"term": f"tmdb:{tmdb_id}"}
        api_response = self._make_request("GET", "series/lookup", params=lookup_params)
        
        if not api_response.success:
            return api_response # Propagate the error response
        
        # Sonarr specific error handling for list of errors if they were returned with a 2xx status
        # but are actually application-level errors (though usually these come with 4xx/5xx)
        # The new Api class puts the parsed JSON error directly into error['details'] for HTTPError.
        # For successful responses, if Sonarr returns a list of error objects in `data`,
        # we might want to format them here or ensure the calling code handles it.
        # However, the `_make_request` in `Api` class already handles JSON decoding for success.
        # If Sonarr returns a list of errors with a 200 OK, it would be in `api_response.data`.
        # The current logic below assumes `api_response.data` is the list of series for a successful lookup.

        # Check if the data from a successful call is valid
        if not api_response.data or not isinstance(api_response.data, list) or len(api_response.data) == 0:
            msg = f"Series with TMDB ID {tmdb_id} not found in Sonarr's lookup or lookup returned empty/invalid."
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=404, error={"details": "Lookup returned no results."})
        
        # If successful and data is valid, update the data field with the first series
        api_response.data = api_response.data[0]
        return api_response

    def add_media(self, tmdb_id: str, quality_profile_id: int, root_dir_path: str = "/tv", 
                  language_profile_id: int = 1, season_folder: bool = True, 
                  monitor: bool = True, search_for_missing: bool = True) -> APIResponse:
        """Add a series to Sonarr using IMDB ID.
        
        Args:
            tmdb_id (str): The TMDB ID of the series to add
            quality_profile_id (int): The ID of the quality profile to use
            root_dir_path (str): The Root Directory path in Sonarr. Defaults to "/tv"
            language_profile_id (int, optional): The ID of the language profile. Defaults to 1=English
            season_folder (bool, optional): Whether to create season folders. Defaults to True
            monitor (bool, optional): Defaults to True
            search_for_missing (bool, optional): Whether to search for missing episodes. Defaults to True
            
        Returns:
            APIResponse: An APIResponse object. If successful, `data` contains the Sonarr response.
        """
        lookup_response = self.lookup_media(tmdb_id)
        if not lookup_response.success:
            return lookup_response # Propagate error from lookup

        series_data = lookup_response.data # This is now the series details dict
        
        # Prepare the payload with series details
        data = {
            **series_data,
            "title": series_data["title"],
            "tmdbId": tmdb_id,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_dir_path,
            "languageProfileId": language_profile_id,
            "seasonFolder": season_folder,
            "monitored": monitor,
            "addOptions": {
                "searchForMissingEpisodes": search_for_missing,
            },
            "titleSlug": series_data["titleSlug"],
            "images": series_data["images"],
            "seasons": series_data["seasons"],
        }

        self.logger.info(f"Sonarr request: {json.dumps(data, indent=2)}")
        return self._make_request("POST", "series", data=data)

    def delete_media(self, id: str) -> APIResponse:
        self.logger.info(f"Deleting Sonarr series with Sonarr ID: {id} ")
        return self._make_request("DELETE", f"series/{id}")

    def get_quality_profiles(self, default_profile_id: Optional[int] = None) -> APIResponse:
        """Get all quality profiles configured in Sonarr with their allowed qualities.
        
        Returns:
            Optional[List[Dict[str, Any]]]: List of simplified quality profiles or None on error.
            Each profile contains:
                - id: The profile ID
                - name: The profile name
                - allowed_qualities: List of allowed quality names
        """
        profiles_response = self._make_request("GET", "qualityprofile")
        if not profiles_response.success:
            return profiles_response # Propagate error

        if not profiles_response.data or not isinstance(profiles_response.data, list):
            self.logger.warning("No quality profiles data received or data is not a list.")
            return APIResponse(success=False, message="No quality profiles data received or in unexpected format.", status_code=profiles_response.status_code)

        simplified_profiles = []
        for profile in profiles_response.data:
            allowed_qualities = []
            for item in profile.get('items', []):
                # Check if the item has a direct allowed flag
                if item.get('allowed', False):
                    # Try to get the quality name, fallback to item name if available
                    quality_name = (item.get('quality', {}).get('name') or 
                                 item.get('name') or 
                                 f"Resolution {item.get('quality', {}).get('resolution')}p")
                    allowed_qualities.append(quality_name)
            
            simplified_profiles.append({
                'id': profile['id'],
                'name': profile['name'],
                'allowed_qualities': allowed_qualities,
                'is_default': profile['id'] == default_profile_id if default_profile_id is not None else False
            })
            
        return APIResponse(success=True, data=simplified_profiles, status_code=profiles_response.status_code)

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Sonarr provider.
        """
        return {
            "enabled": {"value": True, "type": SettingType.BOOLEAN, "description": "Enable or disable Sonarr integration."},
            "url": {"value": "http://sonarr:8989", "type": SettingType.URL, "description": "Sonarr server URL", "required": True},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Sonarr API key", "required": True},
            "default_quality_profile_id": {"value": None, "type": SettingType.INTEGER, "description": "Sonarr Default quality profile ID"}, # Corrected description from Radarr to Sonarr
            "root_dir_path": {"value": "/tv", "type": SettingType.STRING, "description": "Root directory path for Sonarr"},
            "base_provider": {"value": "request", "type": SettingType.STRING, "show": False, "description": "Base Provider Type."},
        }
