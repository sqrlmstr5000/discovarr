import json
import logging
from typing import Optional, Dict, Any

from base.request_provider_base import RequestProviderBase
from services.response import APIResponse 
from services.models import SettingType 

class JellyseerrProvider(RequestProviderBase):
    PROVIDER_NAME = "jellyseerr"

    def __init__(self, url: str, api_key: str):
        """Initialize Jellyseerr client.

        Args:
            url (str): The URL of your Jellyseerr server (e.g., "http://your-jellyseerr-server:5055")
            api_key (str): Your Jellyseerr API key
        """
        super().__init__(url=url, api_key=api_key, api_key_header_name="X-Api-Key", api_base_path="api/v1")
        self.logger = logging.getLogger(__name__)

    def get_users(self, displayName: Optional[str] = None) -> APIResponse:
        """
        Retrieves all users from Jellyseerr.

        Returns:
            APIResponse: An object containing the list of users or error information.
                         If successful, `data` will contain the 'results' array from the response.
        """
        params = {
            "skip": 0, 
            "take": 100
        }
        
        self.logger.info("Fetching all users from Jellyseerr.")
        response = self._make_request("GET", "user", params=params)
        if response.success and isinstance(response.data, dict):
            all_users = response.data.get("results", [])
            if displayName:
                self.logger.info(f"Filtering users for displayName: {displayName}")
                filtered_users = [
                    user for user in all_users if user.get("displayName") == displayName
                ]
                response.data = filtered_users
            else:
                response.data = all_users
        elif response.success and not isinstance(response.data, dict):
            self.logger.warning(f"Jellyseerr /user endpoint returned unexpected data format: {type(response.data)}")
            return APIResponse(success=False, message="Unexpected data format from Jellyseerr /user endpoint.", status_code=response.status_code, data=response.data)
        return response

    # --- Implementation of RequestProviderBase abstract methods ---

    def lookup_media(self, tmdb_id: int, media_type: str, **identifiers: Dict[str, Any]) -> APIResponse:
        """
        Looks up a media item using various identifiers.
        Supports 'term' for general search, or 'tmdb_id' and 'media_type' for specific discovery.

        Args:
            **identifiers: Keyword arguments. Expected:
                           - term (str): Search term for general lookup.
                           - tmdb_id (int): TMDB ID for specific lookup.
                           - media_type (str): "movie" or "tv", required if tmdb_id is used.

        Returns:
            APIResponse: An object containing the details of the found media item(s) or error information.
        """
        title = identifiers.get("title")

        if tmdb_id and media_type:
            if media_type not in ["movie", "tv"]:
                msg = "Invalid media_type. Must be 'movie' or 'tv'."
                self.logger.error(msg)
                return APIResponse(success=False, message=msg, status_code=400)
            self.logger.info(f"Jellyseerr searching for 'tmdb_id: {tmdb_id}' with media_type: {media_type}")
            search_response = self._make_request("GET", f"{media_type}/{tmdb_id}")

            if search_response.success and isinstance(search_response.data, dict):
                results = search_response.data
                if results:
                    return APIResponse(success=True, data=results, status_code=search_response.status_code)
                
                # If no item with matching mediaType was found
                msg = f"No {media_type} found for '{title}' in Jellyseerr search results."
                self.logger.info(msg)
                return APIResponse(success=False, message=msg, status_code=404, data=[]) # Return empty list for data
            elif not search_response.success:
                return search_response # Propagate error from _make_request
        else:
            msg = "Either 'title' or both 'tmdb_id' and 'media_type' must be provided for lookup."
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=400)

    def add_media(
        self,
        tmdb_id: int,
        media_type: str,
        quality_profile_id: Optional[int] = None, # Mapped to target_profile_id
        root_folder_path: Optional[str] = None,   # Mapped to target_root_folder
        monitor: Optional[bool] = True,
        add_options: Optional[Dict[str, Any]] = None       # Can be used for is_4k, seasons, user_id, serverId
    ) -> APIResponse:
        """
        Adds a new media item request to Jellyseerr.
        This adapts the generic add_media interface to Jellyseerr's request_media functionality.

        Args:
            item_info (Dict[str, Any]): Metadata of the item to add.
                                        Expected to contain 'mediaType' and 'id' (as tmdb_id).
            quality_profile_id (Optional[int]): The Jellyseerr profile ID to use.
            root_folder_path (Optional[str]): The specific root folder path.
            monitoring_options (Optional[Dict[str, Any]]): Options for monitoring (largely ignored by Jellyseerr's direct request).
            add_options (Optional[Dict[str, Any]]): Additional options for Jellyseerr:
                                         'is_4k' (bool), 'seasons' (list[int]),
                                         'user_id' (int), 'target_server_id' (int).

        Returns:
            APIResponse: Result of the request operation.
        """
        add_opts = add_options or {}
        media_id = None
        is_4k = add_opts.get("is_4k", False)
        target_server_id = add_opts.get("target_server_id", 0)
        target_profile_id = quality_profile_id
        target_root_folder = root_folder_path
        user_id = add_opts.get("user_id")

        if media_type not in ["movie", "tv"]:
            msg = "Invalid media_type. Must be 'movie' or 'tv'."
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=400, error={"details": msg})
        
        # Lookup the media by title, Jellyseerr /request requires the internal mediaId
        lookup = self.lookup_media(tmdb_id=tmdb_id, media_type=media_type)
        if lookup.success:
            lookup_data = lookup.data
            if lookup_data:
                self.logger.debug(f"Using lookup data for Jellyseerr request: {json.dumps(lookup_data, indent=2)}")
                tmdb_id = lookup_data.get("id")  # Assuming 'id' is the TMDB ID in Jellyseerr's response
                tvdb_id = None
                media_info = lookup_data.get("mediaInfo")
                
                # If mediaInfo is not available, try externalIds
                if not media_info:
                    self.logger.debug("mediaInfo not found in lookup data, checking externalIds.")
                    media_info = lookup_data.get("externalIds") # externalIds might contain tvdbId directly

                if media_info:
                    self.logger.debug(f"Media info from lookup: {json.dumps(media_info, indent=2)}")
                    tvdb_id = media_info.get("tvdbId")
                else:
                    self.logger.debug("No media info from lookup.")

                # Extract season numbers if media_type is 'tv' and seasons data is available
                seasons_to_request = []
                if media_type == "tv" and lookup_data.get("seasons"):
                    seasons_data = lookup_data.get("seasons", [])
                    seasons_to_request = [s.get("seasonNumber") for s in seasons_data if s.get("seasonNumber") is not None]
                    self.logger.debug(f"Extracted season numbers for TV request: {seasons_to_request}")

            payload: Dict[str, Any] = {
                "mediaType": media_type,
                "mediaId": tmdb_id, # Jellyseerr uses mediaId for tmdb_id
                "is4k": is_4k,
            }

            if user_id is not None:
                payload["userId"] = user_id 

            if target_server_id is not None:
                payload["serverId"] = target_server_id
            if target_profile_id is not None:
                payload["profileId"] = target_profile_id
            if target_root_folder is not None:
                payload["rootFolder"] = target_root_folder # Or "rootFolderPath" - check Jellyseerr API docs

            if media_type == "tv":
                if tvdb_id is not None:
                    payload["tvdbId"] = tvdb_id
                
                if seasons_to_request: # Add seasons to payload if any were extracted
                    payload["seasons"] = seasons_to_request

            self.logger.info(f"Jellyseerr request payload: {json.dumps(payload, indent=2)}")
            # The endpoint for creating requests is typically just "/request"
            api_response = self._make_request("POST", "request", data=payload)

            if not api_response.success:
                # The error details from _make_request are already in api_response.error
                self.logger.error(f"Failed to request media via Jellyseerr {media_type}/{tmdb_id}: {api_response.message} - {api_response.error.get('details') if api_response.error else 'No details'}", exc_info=True)
                return api_response

            self.logger.info(f"Jellyseerr request successful for {media_type}/{tmdb_id}. Response: {api_response.data}")
            return api_response
        else:
            self.logger.error(f"Failed to lookup media via Jellyseerr {media_type}/{tmdb_id}: {lookup.message} - {lookup.error.get('details') if lookup.error else 'No details'}", exc_info=True)
            return None

    def delete_media(self, request_id: int) -> APIResponse:
        """
        Deletes a specific media request from Jellyseerr by its request ID.

        Args:
            request_id (int): The unique ID of the request to delete in Jellyseerr.

        Returns:
            APIResponse: Result of the deletion operation.
        """
        self.logger.info(f"Attempting to delete Jellyseerr request with ID: {request_id}")
        delete_response = self._make_request("DELETE", f"request/{request_id}")

        if delete_response.success:
            self.logger.info(f"Successfully deleted Jellyseerr request ID: {request_id}")
        else:
            self.logger.error(f"Failed to delete Jellyseerr request ID: {request_id}. Error: {delete_response.message}")
        
        return delete_response
    
    def get_quality_profiles(self) -> APIResponse:
        """
        Retrieves quality profiles. Jellyseerr manages these internally
        based on its Sonarr/Radarr configurations, so this method
        indicates that direct profile listing like Sonarr/Radarr isn't applicable.
        """
        self.logger.info("Jellyseerr manages quality profiles internally; direct listing is not applicable.")
        return APIResponse(
            success=True, # Or False, depending on how "not applicable" should be treated
            data=[],
            message="Jellyseerr manages quality profiles internally via its Sonarr/Radarr configurations."
        )

    def get_radarr_quality_profiles(self) -> APIResponse:
        """
        Retrieves Radarr quality profiles from the default configured Radarr server in Jellyseerr.
        """
        self.logger.info("Fetching configured Radarr servers from Jellyseerr.")
        radarr_servers_response = self._make_request("GET", "service/radarr")

        if not radarr_servers_response.success:
            self.logger.error(f"Failed to fetch Radarr servers from Jellyseerr: {radarr_servers_response.message}")
            return radarr_servers_response

        if not radarr_servers_response.data or not isinstance(radarr_servers_response.data, list):
            msg = "No Radarr servers configured in Jellyseerr or unexpected response format."
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=404)

        default_server = next((server for server in radarr_servers_response.data if server.get("isDefault")), None)
        
        if not default_server:
            msg = "No default Radarr server found in Jellyseerr configuration."
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=404)

        radarr_id = default_server.get("id")
        if radarr_id is None: # Check explicitly for None, as 0 is a valid ID
            msg = "Default Radarr server found but it is missing an ID."
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=500)

        self.logger.info(f"Found default Radarr server '{default_server.get('name')}' (ID: {radarr_id}). Fetching its detailed configuration to extract quality profiles.")
        
        # Make a new call to get the detailed server configuration
        detailed_server_response = self._make_request("GET", f"service/radarr/{radarr_id}")

        if not detailed_server_response.success:
            self.logger.error(f"Failed to fetch detailed Radarr server config for ID {radarr_id}: {detailed_server_response.message}")
            return detailed_server_response # Propagate error

        detailed_server_data = detailed_server_response.data
        if not isinstance(detailed_server_data, dict):
            msg = f"Detailed Radarr server config for ID {radarr_id} returned unexpected format. Expected dict, got {type(detailed_server_data)}"
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=500, data=[])

        # Quality profiles are available in the detailed server object
        profiles = detailed_server_data.get("profiles", [])

        if not isinstance(profiles, list):
            msg = f"Quality profiles for Radarr server ID {radarr_id} are not in expected list format. Got: {type(profiles)}"
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=500, data=[])
        
        self.logger.info(f"Successfully extracted {len(profiles)} quality profiles from default Radarr server ID {radarr_id}.")
        return APIResponse(success=True, data=profiles, status_code=200)

    def get_sonarr_quality_profiles(self) -> APIResponse:
        """
        Retrieves Sonarr quality profiles from the default configured Sonarr server in Jellyseerr.
        """
        self.logger.info("Fetching configured Sonarr servers from Jellyseerr.")
        sonarr_servers_response = self._make_request("GET", "service/sonarr")

        if not sonarr_servers_response.success:
            self.logger.error(f"Failed to fetch Sonarr servers from Jellyseerr: {sonarr_servers_response.message}")
            return sonarr_servers_response

        if not sonarr_servers_response.data or not isinstance(sonarr_servers_response.data, list):
            msg = "No Sonarr servers configured in Jellyseerr or unexpected response format."
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=404)

        self.logger.debug(f"Fetched Sonarr servers: {sonarr_servers_response.data}")
        default_server = next((server for server in sonarr_servers_response.data if server.get("isDefault")), None)
        self.logger.debug(f"Default Sonarr server: {default_server}")
        
        if not default_server:
            msg = "No default Sonarr server found in Jellyseerr configuration."
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=404)

        sonarr_id = default_server.get("id")
        if sonarr_id is None: # Check explicitly for None, as 0 is a valid ID
            msg = "Default Sonarr server found but it is missing an ID."
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=500)

        self.logger.info(f"Found default Sonarr server '{default_server.get('name')}' (ID: {sonarr_id}). Fetching its detailed configuration to extract quality profiles.")

        # Make a new call to get the detailed server configuration
        detailed_server_response = self._make_request("GET", f"service/sonarr/{sonarr_id}")

        if not detailed_server_response.success:
            self.logger.error(f"Failed to fetch detailed Sonarr server config for ID {sonarr_id}: {detailed_server_response.message}")
            return detailed_server_response # Propagate error

        detailed_server_data = detailed_server_response.data
        if not isinstance(detailed_server_data, dict):
            msg = f"Detailed Sonarr server config for ID {sonarr_id} returned unexpected format. Expected dict, got {type(detailed_server_data)}"
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=500, data=[])

        # Quality profiles are available in the detailed server object
        profiles = detailed_server_data.get("profiles", [])

        if not isinstance(profiles, list):
            msg = f"Quality profiles for Sonarr server ID {sonarr_id} are not in expected list format. Got: {type(profiles)}"
            self.logger.warning(msg)
            return APIResponse(success=False, message=msg, status_code=500, data=[])
        
        self.logger.info(f"Successfully extracted {len(profiles)} quality profiles from default Sonarr server ID {sonarr_id}.")
        return APIResponse(success=True, data=profiles, status_code=200)

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Jellyseerr provider.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Jellyseerr integration."},
            "url": {"value": "http://jellyseerr:5055", "type": SettingType.URL, "description": "Jellyseerr server URL (e.g., http://localhost:5055).", "required": True},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Jellyseerr API key.", "required": True},
            "default_user": {"value": None, "type": SettingType.STRING, "description": "Jellyseerr Default User to use when making requests, refers to the Jellyseerr displayName property.", "required": True},
            "default_radarr_quality_profile_id": {"value": None, "type": SettingType.INTEGER, "description": "Default Radarr quality profile ID"},
            "default_sonarr_quality_profile_id": {"value": None, "type": SettingType.INTEGER, "description": "Default Sonarr quality profile ID"},
            "base_provider": {"value": "request", "type": SettingType.STRING, "show": False, "description": "Base Provider Type (e.g., request, library, llm)."},
        }