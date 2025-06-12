import requests
import json
import logging
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timezone

# Import plexapi
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest, Unauthorized 
from plexapi.utils import toJson
from plexapi.media import Media # For type hinting if needed
from plexapi.video import Movie, Show, Episode, MovieHistory, EpisodeHistory
from services.models import ItemsFiltered, LibraryUser, SettingType
from plexapi.server import SystemAccount
from base.library_provider_base import LibraryProviderBase # Import the base class


# Helper function to convert datetime object to ISO 8601 string
def _datetime_to_iso(dt: Optional[datetime]) -> Optional[str]:

    if dt is None:
        return None
    # Ensure datetime is timezone-aware (UTC) before formatting
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

# Helper function to convert epoch timestamp to ISO 8601 string
def _epoch_to_iso(epoch_timestamp: Optional[Union[int, float]]) -> Optional[str]:
    if epoch_timestamp is None:
        return None
    # Ensure it's treated as seconds. Plex usually provides seconds.
    dt_object = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    return dt_object.isoformat().replace("+00:00", "Z")

class PlexProvider(LibraryProviderBase):
    """
    A class to interact with the Plex API.
    Utilizes the python-plexapi library for communication with a Plex server.
    """
    PROVIDER_NAME = "plex"

    def __init__(self, plex_url: str, plex_api_key: str, limit: int = 10):
        """
        Initializes the Plex class with API configurations.

        Args:
            plex_url (str): The base URL of the Plex server (e.g., http://localhost:32400).
            plex_api_key (str): The X-Plex-Token for authentication.
            limit (int): Default limit for API requests.
        """
        self.logger = logging.getLogger(__name__)
        self.plex_url = plex_url
        self.plex_api_key = plex_api_key
        self.limit = limit
        self.server: Optional[PlexServer] = None
        try:
            # plexapi.server.PlexServer can take requests.Session() object for custom configurations
            # For simplicity, we'll let it create its own.
            self.server = PlexServer(self.plex_url, self.plex_api_key)
            # Test connection by fetching server identifier or version
            self.logger.info(f"Successfully connected to Plex server: {self.server.friendlyName} (Version: {self.server.version})")
        except Unauthorized:
            self.logger.error(f"Plex connection unauthorized: Invalid token or insufficient permissions for {self.plex_url}.")
            self.server = None # Ensure server is None if connection failed
        except requests.exceptions.ConnectionError as e: # plexapi might raise this via requests
            self.logger.error(f"Plex connection failed for {self.plex_url}: {e}")
            self.server = None
        except Exception as e: # Catch any other plexapi or general exceptions during init
            self.logger.error(f"Failed to initialize Plex server connection to {self.plex_url}: {e}", exc_info=True)
            self.server = None

    @property
    def name(self) -> str:
        """Returns the name of the library provider."""
        return self.PROVIDER_NAME

    def get_users(self) -> Optional[List[LibraryUser]]:
        """
        Get all managed Plex accounts (users under the main account).

        Returns:
            Optional[List[LibraryUser]]: List of user account objects,
                                         or None if an error occurs or server not connected.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get users.")
            return None
        try:
            accounts: List[SystemAccount] = self.server.systemAccounts()
            user_list: List[LibraryUser] = []
            for acc in accounts:
                if acc.id != 0:
                    user_list.append(LibraryUser(
                        id=str(acc.id),
                        name=acc.name,
                        thumb=acc.thumb,
                        source_provider=self.PROVIDER_NAME
                    ))
            return user_list
        except Exception as e:
            self.logger.error(f"Error fetching Plex users: {e}", exc_info=True)
            return None

    def get_user_by_name(self, username: str) -> Optional[LibraryUser]:
        """
        Looks up a managed Plex user account ID using the provided username.

        Returns:
            Optional[LibraryUser]: The user account object if found, or None.
        """
        users = self.get_users() # This now returns List[LibraryUser]
        if users:
            for user_obj in users:
                if user_obj.name == username:
                    return user_obj
        self.logger.info(f"User '{username}' not found among managed accounts.")
        return None

    def get_recently_watched(self, user_id: str, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """
        Retrieves recently watched items from Plex for a specific user ID.
        Returns a list of ItemsFiltered.

        Args:
            user_id (str): The ID of the Plex user (from /accounts).
            limit (int, optional): The maximum number of items to retrieve. Defaults to the class default.
        Returns:
            Optional[List[ItemsFiltered]]: A list of filtered recently watched items, or None on error.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get recently watched.")
            return None
        if not user_id:
            self.logger.error("Plex User ID is required for get_recently_watched.")
            return None
        
        try:
            user_id_int = int(user_id)
        except ValueError:
            self.logger.error(f"Invalid Plex User ID format: {user_id}. Must be an integer.")
            return None

        try:
            # Pass 'limit' directly to maxresults. If limit is None, plexapi handles it as no limit.
            history_items: List[Media] = self.server.history(accountID=user_id_int, maxresults=limit)
            
            watched_videos = [item for item in history_items if isinstance(item, (MovieHistory, EpisodeHistory))]
            raw_items_json = json.loads(toJson(watched_videos)) if watched_videos else []

            # Filter and transform to ItemsFiltered
            filtered_items = self.get_items_filtered(items=raw_items_json)
            if isinstance(filtered_items, list) and all(isinstance(i, ItemsFiltered) for i in filtered_items):
                return filtered_items
            self.logger.warning("get_items_filtered did not return a list of ItemsFiltered for Plex recently watched.")
            return []

        except NotFound:
            self.logger.info(f"No watch history found for user ID {user_id}.")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching recently watched for user ID {user_id}: {e}", exc_info=True)
            return None
        
    def get_favorites(self, user_id: str, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """
        Retrieves "favorite" items (highly rated: 9 or 10 out of 10) for the user associated with the token.
        The plex_user_id is for logging/context, as ratings are tied to the token owner.
        Conforms to LibraryProviderBase, returning List[Dict[str, Any]].

        Args:
            user_id (str): The ID of the Plex user (for context).
            limit (int, optional): The maximum number of items to retrieve. Defaults to the class default.

        Returns:
            Optional[List[ItemsFiltered]]: List of filtered "favorite" items, or None on error.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get favorites.")
            return None
            
        self.logger.info(f"Fetching favorites (highly rated items) for user context (token dependent). User ID hint: {user_id}")
        current_limit = limit if limit is not None else self.limit
        favorites: List[Union[Movie, Show]] = []

        try:
            for section in self.server.library.sections():
                if section.type in ['movie', 'show']:
                    self.logger.debug(f"Searching for favorites in section: {section.title} (Type: {section.type})")
                    items_in_section = section.all() 
                    
                    for item in items_in_section:
                        if len(favorites) >= current_limit:
                            break
                        if hasattr(item, 'userRating') and item.userRating is not None and item.userRating >= 9.0:
                            if isinstance(item, (Movie, Show)): 
                                favorites.append(item)
                    
                    if len(favorites) >= current_limit:
                        break 
            result_favorites = favorites[:current_limit]
            raw_items_json = json.loads(toJson(result_favorites)) if result_favorites else []

            filtered_items = self.get_items_filtered(items=raw_items_json)
            if isinstance(filtered_items, list) and all(isinstance(i, ItemsFiltered) for i in filtered_items):
                return filtered_items
            self.logger.warning("get_items_filtered did not return a list of ItemsFiltered for Plex favorites.")
            return []

        except Exception as e:
            self.logger.error(f"Error fetching favorites: {e}", exc_info=True)
            return None

    def get_items_filtered(self, items: Optional[List[Dict[str, Any]]], attribute_filter: Optional[str] = None) -> Union[List[ItemsFiltered], List[str]]:
        """
        Filters Plex items (dictionaries from JSON), consolidating episodes under series and ensuring uniqueness.
        Updates to the most recent last_played_date if duplicates are found (for history source).
        Conforms to LibraryProviderBase.

        Args:
            items (Optional[List[Dict[str, Any]]]): List of raw Plex item dictionaries (from toJson utility).
            attribute_filter (Optional[str]): If 'name', returns a list of names. Otherwise, List[ItemsFiltered].
        Returns:
            Union[List[ItemsFiltered], List[str]]: Filtered items. Empty list if input is None/empty.
        """
        if not items:
            self.logger.debug(f"No Plex items provided for filtering. Returning empty list.")
            return []

        processed_media_map: Dict[str, ItemsFiltered] = {}

        for item in items:
            media_name: Optional[str] = None
            consolidated_media_id: Optional[str] = None 
            output_media_type: Optional[str] = None  # 'movie' or 'tv'
            
            current_last_played_date_iso: Optional[str] = None
            play_count_val: Optional[int] = None
            is_favorite_val: Optional[bool] = None
            poster_url_val: Optional[str] = None
            thumb_path: Optional[str] = None
            
            #
            # Leave for manual debugging
            #
            #self.logger.debug(f"Plex raw item: {json.dumps(item, indent=2)}")
            # Determine item type from dictionary keys (based on plexapi.utils.toJson output)
            item_type_from_dict = item.get('type') # 'movie', 'show', 'episode'

            if item_type_from_dict == 'episode':
                media_name = item.get('grandparentTitle') # Show title
                key = item.get('grandparentKey')
                consolidated_media_id = str(key.split('/')[-1]) 
                output_media_type = "tv" 
                thumb_path = item.get('grandparentThumb')
            elif item_type_from_dict == 'show': 
                media_name = item.get('title')
                key = item.get('key')
                consolidated_media_id = str(key.split('/')[-1]) 
                output_media_type = "tv"
                thumb_path = item.get('thumb')
            elif item_type_from_dict == 'movie': 
                media_name = item.get('title')
                key = item.get('key')
                consolidated_media_id = str(key.split('/')[-1]) 
                output_media_type = "movie"
                thumb_path = item.get('thumb')
            else:
                self.logger.debug(f"Skipping history item with unhandled dict type '{item_type_from_dict}': {item.get('title', 'Unknown Item')}")
                continue
            
            viewed_at_val = None
            if item.get('viewedAt'):
                viewed_at_val = item.get('viewedAt')
            elif item.get('lastViewedAt'):
                viewed_at_val = item.get('lastViewedAt')
            #self.logger.debug(f"Plex ViewedAt (raw value from history item '{media_name}'): {viewed_at_val}, type: {type(viewed_at_val)}")
            if isinstance(viewed_at_val, str):
                try:
                    # Attempt to parse the string as an ISO datetime
                    dt_obj = datetime.fromisoformat(viewed_at_val)
                    current_last_played_date_iso = _datetime_to_iso(dt_obj)
                except ValueError:
                    self.logger.warning(f"Could not parse viewedAt string '{viewed_at_val}' as ISO datetime for Plex history item '{media_name}'.")
                    current_last_played_date_iso = None
            elif isinstance(viewed_at_val, (int, float)):
                # If it's already a number, treat as epoch (plexapi.utils.toJson default for datetime)
                current_last_played_date_iso = _epoch_to_iso(viewed_at_val)
            else:
                current_last_played_date_iso = None
    
            play_count_val = item.get('viewCount')
            user_rating = item.get('userRating')
            if user_rating is not None:
                try:
                    is_favorite_val = float(user_rating) >= 9.0
                except ValueError:
                    self.logger.warning(f"Could not parse userRating '{user_rating}' as float for item '{media_name}'.")
            
            # Get poster URL
            if thumb_path and self.server:
                poster_url_val = self.server.url(thumb_path, includeToken=True) # includeToken=False is often better for caching

            if not media_name:
                self.logger.debug(f"Skipping item due to missing name (media_name is None): {item}")
                continue

            if media_name in processed_media_map:
                existing_pm_item = processed_media_map[media_name]
                if current_last_played_date_iso:
                    if (not existing_pm_item.last_played_date or 
                            current_last_played_date_iso > existing_pm_item.last_played_date):
                        existing_pm_item.last_played_date = current_last_played_date_iso
                
                if play_count_val is not None and existing_pm_item.play_count is None: # Only set if not already set
                    existing_pm_item.play_count = play_count_val
                if is_favorite_val is not None and existing_pm_item.is_favorite is None: # Only set if not already set
                    existing_pm_item.is_favorite = is_favorite_val
            else:
                processed_media_map[media_name] = ItemsFiltered(
                    name=media_name,
                    id=consolidated_media_id,
                    type=output_media_type,
                    last_played_date=current_last_played_date_iso,
                    play_count=play_count_val,
                    is_favorite=is_favorite_val,
                    poster_url=poster_url_val
                )

        if attribute_filter and attribute_filter.lower() == "name":
            return [pm_item.name for pm_item in processed_media_map.values()]
        else:
            return list(processed_media_map.values())

    def _get_all_items_raw(self) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves all movie and TV show (series) items from the Plex library.
        Internal helper to fetch items and convert them to JSON dictionaries.

        Returns:
            Optional[List[Dict[str, Any]]]: List of all movie and show items as dictionaries.
                                 Returns None on error or server not connected.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get all items.")
            return None
            
        all_media_items: List[Union[Movie, Show]] = []
        try:
            for section in self.server.library.sections():
                if section.type == 'movie':
                    self.logger.debug(f"Fetching all movies from section: {section.title}")
                    all_media_items.extend(section.all()) # type: ignore # section.all() returns List[Movie]
                elif section.type == 'show':
                    self.logger.debug(f"Fetching all shows from section: {section.title}")
                    all_media_items.extend(section.all()) # type: ignore # section.all() returns List[Show]
            
            return json.loads(toJson(all_media_items)) if all_media_items else []
        except Exception as e:
            self.logger.error(f"Error fetching all items from Plex library: {e}", exc_info=True)
            return None

    def get_all_items_filtered(self, attribute_filter: Optional[str] = None) -> Optional[Union[List[ItemsFiltered], List[str]]]:
        """
        Retrieves all movie/show items from Plex as dictionaries and filters them.
        Conforms to LibraryProviderBase.

        Args:
            attribute_filter (Optional[str]): If 'name', returns a list of names. 
                                              Otherwise, list of ItemsFiltered.
        Returns:
            Optional[Union[List[ItemsFiltered], List[str]]]: Filtered list or None on error.
        """
        raw_plex_item_dicts = self._get_all_items_raw()
        if raw_plex_item_dicts is None:
            self.logger.warning("No items returned from Plex library (error state or not connected) for get_all_items_filtered.")
            return None
        
        self.logger.debug(f"Retrieved {len(raw_plex_item_dicts)} raw Plex item dictionaries from library for filtering.")
        return self.get_items_filtered(items=raw_plex_item_dicts, attribute_filter=attribute_filter)

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Plex provider.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Plex integration."},
            "url": {"value": "http://plex:32400", "type": SettingType.URL, "description": "Plex server URL", "required": True}, # Already marked
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Plex X-Plex-Token", "required": True}, # Already marked
            "default_user": {"value": None, "type": SettingType.STRING, "description": "Plex Default User to use for watch history and favorites, if None use all."},
            "enable_media": {"value": True, "type": SettingType.BOOLEAN, "description": "Enable media from this library provider. All library media will be included the {{media_exclude}} template variable."},
            "enable_history": {"value": True, "type": SettingType.BOOLEAN, "description": "Enable watch history from this library provider. Used for the {{watch_history}} template variable."},
            "base_provider": {"value": "library", "type": SettingType.STRING, "show": False, "description": "Base Provider Type"},
        }
