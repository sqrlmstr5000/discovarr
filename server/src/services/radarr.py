import json
import logging
from typing import Optional, Dict, Any
from .response import APIResponse # Import the APIResponse class
from .api import Api # Import the new Api class

class Radarr(Api):
    def __init__(self, url: str, api_key: str, root_dir_path: str):
        """Initialize Radarr client.
        
        Args:
            url (str): The URL of your Radarr server (e.g., "http://your-radarr-server:7878")
            api_key (str): Your Radarr API key
        """
        super().__init__(url=url, api_key=api_key, api_key_header_name="X-Api-Key", api_base_path="api/v3")
        self.logger = logging.getLogger(__name__)
        self._root_dir_path = root_dir_path
        # self.url, self.api_key, and self.headers are now managed by the Api base class

    def get_quality_profiles(self, default_profile_id: Optional[int] = None) -> APIResponse:
        """Get all quality profiles configured in Radarr.
        
        Returns:
            APIResponse: An APIResponse object. If successful, `data` contains a list of 
                         simplified quality profiles. Each profile contains:
                            - id: The profile ID
                            - name: The profile name
                            - allowed_qualities: List of allowed quality names
                            - is_default: Boolean indicating if it's the default
        """
        profiles_response = self._make_request("GET", "qualityprofile")
        if not profiles_response.success:
            return profiles_response # Propagate error

        if not profiles_response.data or not isinstance(profiles_response.data, list):
            self.logger.warning("No quality profiles data received from Radarr or data is not a list.")
            return APIResponse(
                success=False, 
                message="No quality profiles data received or in unexpected format from Radarr.", 
                status_code=profiles_response.status_code
            )
            
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

    def lookup_movie(self, tmdb_id: int) -> APIResponse:
        """Look up movie details from TMDB ID.
        
        Args:
            tmdb_id (int): The TMDb ID of the movie
            
        Returns:
            APIResponse: An APIResponse object. If successful, `data` contains movie details.
        """
        # Radarr's lookup endpoint for a single movie by TMDB ID usually returns a single movie object, not a list.
        api_response = self._make_request("GET", "movie/lookup/tmdb", params={"tmdbId": tmdb_id})

        if not api_response.success:
            return api_response # Propagate error

        # Check if the data from a successful call is valid (Radarr returns a single object for this lookup)
        if not api_response.data or not isinstance(api_response.data, dict): # Expecting a dict
            msg = f"Movie with TMDB ID {tmdb_id} not found in Radarr's lookup or lookup returned invalid data."
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=404, error={"details": "Lookup returned no or invalid results."})
        
        return api_response

    def add_movie(self, tmdb_id: int, quality_profile_id: int, 
                 monitor: bool = True, search_for_movie: bool = True) -> APIResponse:
        """Add a movie to Radarr using TMDb ID.
        
        Args:
            tmdb_id (int): The TMDb ID of the movie to add
            quality_profile_id (int): The ID of the quality profile to use
            root_dir_path (str): The Root Directory path in Radarr. Defaults to "/movies"
            monitor (bool, optional): Whether to monitor the movie. Defaults to True
            search_for_movie (bool, optional): Whether to search for movie after adding. Defaults to True
            
        Returns:
            APIResponse: An APIResponse object. If successful, `data` contains the Radarr response.
        """
        # First lookup the movie details
        lookup_response = self.lookup_movie(tmdb_id)
        if not lookup_response.success:
            return lookup_response # Propagate error from lookup

        movie_info = lookup_response.data # This is now the movie details dict
        # Prepare the payload with movie details
        data = {
            **movie_info,  # Include all movie details from lookup
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": self._root_dir_path,
            "monitored": monitor,
            "addOptions": {
                "searchForMovie": search_for_movie,
            },
        }

        self.logger.info(f"Radarr add movie request: {json.dumps(data, indent=2)}")
        return self._make_request("POST", "movie", data=data)
