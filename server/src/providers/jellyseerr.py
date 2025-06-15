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

    def lookup_media(self, **identifiers: Any) -> APIResponse:
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
        tmdb_id = identifiers.get("tmdb_id")
        media_type = identifiers.get("media_type") # "movie" or "tv"

        if title and media_type:
            if media_type not in ["movie", "tv"]:
                msg = "Invalid media_type. Must be 'movie' or 'tv'."
                self.logger.error(msg)
                return APIResponse(success=False, message=msg, status_code=400)
            self.logger.info(f"Jellyseerr searching for '{title}' with media_type: {media_type}")
            search_response = self._make_request("GET", "search", params={"query": title})

            if search_response.success and isinstance(search_response.data, dict):
                results = search_response.data.get("results", [])
                for item in results:
                    if item.get("mediaType") == media_type:
                        self.logger.info(f"Found matching {media_type} for '{title}': {item.get('title') or title}")
                        # Return the first matching item
                        return APIResponse(success=True, data=item, status_code=search_response.status_code)
                
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
        item_info: Dict[str, Any],
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
        media_type = item_info.get("mediaType")
        title = item_info.get("title")
        is_4k = add_opts.get("is_4k", False)
        target_server_id = add_opts.get("target_server_id", 0)
        target_profile_id = quality_profile_id
        target_root_folder = root_folder_path
        user_id = add_opts.get("user_id")

        if not media_type or not title:
            msg = "item_info must contain 'mediaType' and 'title'"
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=400)

        if media_type not in ["movie", "tv"]:
            msg = "Invalid media_type. Must be 'movie' or 'tv'."
            self.logger.error(msg)
            return APIResponse(success=False, message=msg, status_code=400, error={"details": msg})
        
        # Lookup the media by title, Jellyseerr /request requires the internal mediaId
        lookup = self.lookup_media(title=title, media_type=media_type)
        if lookup.success:
            lookup_data = lookup.data
            if lookup_data:
                self.logger.debug(f"Using lookup data for request: {json.dumps(lookup_data, indent=2)}")
                media_id = lookup_data.get("id")  # Assuming 'id' is the TMDB ID in Jellyseerr's response

            payload: Dict[str, Any] = {
                "mediaType": media_type,
                "mediaId": media_id, # Jellyseerr uses mediaId for tmdb_id
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

            self.logger.info(f"Jellyseerr request payload: {json.dumps(payload, indent=2)}")
            # The endpoint for creating requests is typically just "/request"
            api_response = self._make_request("POST", "request", data=payload)

            if not api_response.success:
                # The error details from _make_request are already in api_response.error
                self.logger.error(f"Failed to request media via Jellyseerr {item_info}: {api_response.message} - {api_response.error.get('details') if api_response.error else 'No details'}", exc_info=True)
                return api_response

            self.logger.info(f"Jellyseerr request successful for {item_info}. Response: {api_response.data}")
            return api_response
        else:
            self.logger.error(f"Failed to lookup media via Jellyseerr {item_info}: {lookup.message} - {lookup.error.get('details') if lookup.error else 'No details'}", exc_info=True)
            return None
    
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
            "base_provider": {"value": "request", "type": SettingType.STRING, "show": False, "description": "Base Provider Type (e.g., request, library, llm)."},
        }