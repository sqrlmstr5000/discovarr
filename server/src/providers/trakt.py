import json
import logging
from typing import Optional, Dict, List, Any, Union, TYPE_CHECKING
from threading import Condition

from trakt import Trakt
from trakt.objects.episode import Episode # Keep for get_items_filtered
from trakt.objects.movie import Movie
from trakt.objects.show import Show
from services.models import ItemsFiltered, SettingType
from base.library_provider_base import LibraryProviderBase

if TYPE_CHECKING:
    from discovarr import Discovarr # For type hinting Discovarr instance
from services.models import LibraryUser # Import LibraryUser

TRAKT_API_VERSION = "2"
TRAKT_BASE_URL = "https://api.trakt.tv"

class TraktProvider(LibraryProviderBase):
    """
    Provider for interacting with Trakt.tv.
    """

    PROVIDER_NAME = "trakt"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: Optional[str] = None, discovarr_app: Optional['Discovarr'] = None, initial_authorization: Optional[Dict[str, Any]] = None):
        """
        Initializes the TraktProvider.
        Args:
            client_id (str): The Trakt Client ID.
            client_secret (str): The Trakt Client Secret.
            redirect_uri (Optional[str]): The OAuth redirect URI.
            discovarr_app (Optional['Discovarr']): Instance of the main Discovarr application.
        """
        self.logger = logging.getLogger(__name__)
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self.discovarr_app = discovarr_app

        self.is_authenticating = Condition()

        self.authorization = None

        # Bind trakt events
        Trakt.on('oauth.token_refreshed', self.on_token_refreshed)

        Trakt.base_url = TRAKT_BASE_URL
        Trakt.api_version = TRAKT_API_VERSION

        Trakt.configuration.defaults.client(
            id=self._client_id,
            secret=self._client_secret
        )

        # Attempt to load stored authorization from settings
        stored_auth_json = None
        if self.discovarr_app and self.discovarr_app.settings:
            stored_auth_json = self.discovarr_app.settings.get('trakt', 'authorization')

        # Used for pytest initialization
        if initial_authorization:
            self.authorization = initial_authorization
            Trakt.configuration.oauth.from_response(self.authorization)
            self.logger.info("TraktProvider initialized with initial authorization.")
        elif stored_auth_json:
            try:
                self.authorization = json.loads(stored_auth_json)
                if self.authorization and 'access_token' in self.authorization:
                    Trakt.configuration.oauth.from_response(self.authorization)
                    self.logger.info("TraktProvider initialized using stored authorization.")
                else:
                    self.logger.warning("Stored Trakt authorization is invalid. Proceeding with interactive authentication.")
                    self.authorization = None # Ensure it's None if invalid
                    self._authenticate()
            except json.JSONDecodeError:
                self.logger.error("Failed to parse stored Trakt authorization. Proceeding with interactive authentication.")
                self.authorization = None # Ensure it's None if invalid
                self._authenticate()
        else:
            self.logger.info("No stored Trakt authorization found. Attempting interactive authentication.")
            self._authenticate() # This will block until authentication completes or fails

    @property
    def name(self) -> str:
        """
        Returns the name of the library provider.
        """
        return "trakt"

    def _authenticate(self):
        """
        Initiates the device authentication flow for Trakt.
        This method is blocking and will wait for authentication to complete or fail.
        This method now returns immediately after initiating the flow.
        The actual authentication (token exchange) happens in a background thread.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - 'success': bool, True if the authentication process was successfully initiated.
                - 'user_code': str, The code the user needs to enter.
                - 'verification_url': str, The URL the user needs to visit.
                - 'message': str, A message describing the outcome or current state.
        """
        # Attempt to acquire the lock. If already held, another auth process is ongoing.
        # The blocking=False ensures it doesn't wait if another thread holds it.
        if not self.is_authenticating.acquire(blocking=False):
            self.logger.info('Authentication has already been started')
            return {"success": False, "user_code": None, "verification_url": None, "message": "Authentication process is already active."}

        # Request new device code
        code = Trakt['oauth/device'].code()
        user_code = code.get('user_code')
        verification_url = code.get('verification_url')

        self.logger.info(f'To authenticate, enter code "{user_code}" at {verification_url}')
        try:
            # Construct device authentication poller
            poller = Trakt['oauth/device'].poll(**code)\
                .on('aborted', self.on_aborted)\
                .on('authenticated', self.on_authenticated)\
                .on('expired', self.on_expired)\
                .on('poll', self.on_poll)
            
            # Start polling for authentication token in a background thread
            poller.start(daemon=True)

            # The lock is released by the callback that finishes the auth process (on_authenticated, on_aborted, on_expired)
            # For this immediate return, we don't release it here if the poller's callbacks need it.
            # However, the initial acquire was to prevent re-entry. We can release it now.
            self.is_authenticating.release()
            
            return {"success": True, "user_code": user_code, "verification_url": verification_url, "message": "Authentication initiated. Follow instructions."}
        except Exception as e:
            self.logger.error(f"Failed to start Trakt authentication poller: {e}", exc_info=True)
            self.is_authenticating.release() # Ensure lock is released on error
            return {"success": False, "user_code": None, "verification_url": None, "message": f"Error initiating authentication: {e}"}

    def on_aborted(self):
        """Device authentication aborted.

        Triggered when device authentication was aborted (either with `DeviceOAuthPoller.stop()`
        or via the "poll" event)
        """

        with self.is_authenticating: # Ensures lock is acquired and released
            self.logger.error('Authentication aborted')
            # Notify any waiters (if any) and release the lock
            self.is_authenticating.notify_all()

    def on_authenticated(self, authorization):
        """Device authenticated.

        :param authorization: Authentication token details
        :type authorization: dict
        """
        with self.is_authenticating:
            # Store authorization for future calls
            self.authorization = authorization
            
            # Configure the Trakt library with the new token
            Trakt.configuration.oauth.from_response(self.authorization)

            # Save the entire authorization object to settings
            if self.discovarr_app and self.discovarr_app.settings:
                self.discovarr_app.settings.set('trakt', 'authorization', json.dumps(self.authorization))
                self.logger.info("Trakt authorization details saved to settings.")

            self.logger.info('Authentication successful - authorization stored.')
            self.logger.debug('Authorization details: %r' % self.authorization)

            self.is_authenticating.notify_all()

    def on_expired(self):
        """Device authentication expired."""
        with self.is_authenticating:
            self.logger.error('Authentication expired')
            self.is_authenticating.notify_all()

    def on_poll(self, callback):
        """Device authentication poll.
        This callback is executed in the poller's thread.

        :param callback: Call with `True` to continue polling, or `False` to abort polling
        :type callback: func
        """
        # self.logger.debug("Trakt authentication polling...") # Can be very verbose
        # Continue polling
        callback(True)

    def on_token_refreshed(self, authorization):
        # OAuth token refreshed, store authorization for future calls
        self.authorization = authorization
        
        # Re-configure the Trakt library with the refreshed token
        Trakt.configuration.oauth.from_response(self.authorization)
        
        # Save new access_token and refresh_token to settings
        if self.discovarr_app and self.discovarr_app.settings and self.authorization:
            self.discovarr_app.settings.set('trakt', 'authorization', json.dumps(self.authorization))
            self.logger.info("Trakt authorization details (refreshed) saved to settings.")

        self.logger.debug('Token refreshed - authorization: %r' % self.authorization)

    def _handle_trakt_exception(self, e: Exception, context: str) -> None:
        """Helper to log Trakt exceptions."""
        self.logger.error(f"Trakt API error during {context}: {e}", exc_info=True)
        if hasattr(e, 'response') and e.response is not None:
            self.logger.error(f"Trakt API Response Status: {e.response.status_code}")
            try:
                self.logger.error(f"Trakt API Response Body: {e.response.json()}")
            except json.JSONDecodeError:
                self.logger.error(f"Trakt API Response Body (not JSON): {e.response.text}")

    def get_users(self) -> Optional[List[LibraryUser]]:
        """
        Retrieves the authenticated Trakt user.
        Trakt is typically single-user in this context (the authenticated user).
        """
        # Ensure that we have authorization details and the Trakt library has an active token.
        if self.authorization and Trakt['oauth'].token:
            try:
                
                # TODO: This doesn't work without the with statement. Why?

                with Trakt.configuration.oauth.from_response(self.authorization):
                    user_settings = Trakt['users/settings'].get()
                    self.logger.debug(f"Retrieved Trakt user settings: {user_settings}")
                    if user_settings and user_settings.get('user'):
                        user_data = user_settings['user']
                        username = user_data.get('username')
                        self.logger.info(f"Retrieved Trakt user profile for: {username}")
                        avatar_url = user_data.get('images', {}).get('avatar', {}).get('full')
                        return [LibraryUser(
                            id=user_data.get("ids", {}).get("slug"),
                            name=username,
                            thumb=avatar_url,
                            source_provider=self.PROVIDER_NAME
                        )]
                self.logger.warning("TraktProvider: Failed to retrieve user profile or profile in unexpected format.")
            except Exception as e:
                self._handle_trakt_exception(e, "get_users")
        else:
            self.logger.warning("TraktProvider: get_users requires an authenticated session (self.authorization is set and Trakt['oauth'].token exists).")
        return None

    def get_user_by_name(self, username: str) -> Optional[LibraryUser]:
        """
        Retrieves the Trakt user if the username matches the authenticated user.
        """
        users = self.get_users()
        if users:
            for user in users:
                if user.name == username:
                    self.logger.info(f"TraktProvider: Found authenticated user matching '{username}'.")
                    return user
        self.logger.info(f"TraktProvider: User '{username}' not found or does not match the authenticated user.")
        return None

    def get_recently_watched(self, user_id: str, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """
        Retrieves recently watched items for the Trakt user.
        'user_id' for Trakt would typically be the authenticated user's ID/slug (e.g., 'me' or actual slug).
        Returns a list of ItemsFiltered.
        """
        if not Trakt['oauth'].token:
            self.logger.warning("TraktProvider: get_recently_watched requires an authenticated session.")
            return None

        get_kwargs = {
            'media': None,  # All types: movies, episodes
            'extended': 'full',
            'pagination': False  # Fetch a single page of results
        }
        if limit is None:
            # With pagination=False and per_page=None, Trakt API's default page limit applies (e.g., 10 items).
            get_kwargs['per_page'] = None
        else:
            # Fetch up to 'limit' items.
            get_kwargs['per_page'] = limit
            # page will use its default of None (first page)

        try:
            # Fetch combined history (movies and episodes)
            history_items_iter = Trakt[f"users/{user_id}/history"].get(**get_kwargs)
            # Convert iterable to list of trakt.Object instances
            raw_watched_items = list(history_items_iter) if history_items_iter else []
            #
            # Leave for manual debugging
            #
            #for item in raw_watched_items:
            #    self.logger.debug(f"Trakt raw item: {json.dumps(item.to_dict(), indent=2)}")
            self.logger.info(f"Retrieved {len(raw_watched_items)} raw recently watched Trakt items for user {user_id}.")

            # Filter and transform to ItemsFiltered
            # get_items_filtered expects a list of trakt.Object, not dicts
            filtered_items = self.get_items_filtered(items=raw_watched_items)
            if isinstance(filtered_items, list) and all(isinstance(i, ItemsFiltered) for i in filtered_items):
                self.logger.debug(f"Trakt filtered items: {filtered_items}")
                return filtered_items
            self.logger.warning("get_items_filtered did not return a list of ItemsFiltered for Trakt recently watched.")
            return []
        except Exception as e:
            self._handle_trakt_exception(e, f"get_recently_watched for user {user_id}")
        return None

    def get_favorites(self, user_id: str, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """
        Retrieves favorite items (e.g., watchlist, personal lists) for the Trakt user.
        'user_id' for Trakt would typically be the authenticated user's ID/slug.
        """
        if not Trakt['oauth'].token:
            self.logger.warning("TraktProvider: get_favorites requires an authenticated session.")
            return None
        
        favorite_items = []
        try:
            # Fetch ratings (Trakt ratings are 1-10: int)
            rated_items_iter = Trakt[f"users/{user_id}/ratings"].get(
                media=None, # All types: movies, episodes
                extended='full',
                per_page=limit,
                pagination=False
                )

            if rated_items_iter:
                raw_favorite_items = list(rated_items_iter)
                self.logger.info(f"Retrieved {len(raw_favorite_items)} raw items from ratings for user {user_id}.")
                # Filter and transform to ItemsFiltered
                filtered_items = self.get_items_filtered(items=raw_favorite_items) # Assuming a source_type for favorites
                if isinstance(filtered_items, list) and all(isinstance(i, ItemsFiltered) for i in filtered_items):
                    self.logger.debug(f"Trakt filtered items: {filtered_items}")
                    return filtered_items
                self.logger.warning("get_items_filtered did not return a list of ItemsFiltered for Trakt favorites.")
                return []

            self.logger.info(f"Ratings for user {user_id} is empty or failed to retrieve.")
            return []
        except Exception as e:
            self._handle_trakt_exception(e, f"get_favorites for user {user_id}")
        return None
    
    def get_items_filtered(self, items: Optional[List[Any]], attribute_filter: Optional[str] = None) -> Union[List[ItemsFiltered], List[str]]:
        """
        Filters a list of raw Trakt media items.
        Items are expected to be trakt.objects (e.g., HistoryItem, Movie, TVShow).
        """
        if not items: # items is List[trakt.Object]
            self.logger.debug("TraktProvider: No items provided for filtering.")
            return []

        processed_media_map: Dict[str, ItemsFiltered] = {}

        for item in items:
            name: Optional[str] = None
            trakt_id_str: Optional[str] = None
            media_type_for_filter: Optional[str] = None # 'movie' or 'tv'
            last_played_date_iso: Optional[str] = None
            play_count_val: Optional[int] = None
            is_favorite_val: bool = False # Default

            if hasattr(item, 'last_watched_at'): # For history items
                last_played_date_iso = item.last_watched_at
            if hasattr(item, 'plays'): # For history items
                play_count_val = item.plays
            if hasattr(item, 'rating') and item.rating is not None and item.rating.value >= 8: # For rated/favorite items
                is_favorite_val = True

            if isinstance(item, Movie):
                name = item.title
                identifier = item.to_identifier()
                self.logger.debug(f"Movie identifier: {json.dumps(identifier, indent=2)}")
                trakt_id_str = str(identifier["ids"].get('tmdb', None))
                media_type_for_filter = "movie"
            elif isinstance(item, Episode): 
                show = item.show
                if show:
                    self.logger.debug(f"Retrieved Show {show.title} from Episode {item}: type: {type(show)} {show}")
                    name = show.title
                    identifier = show.to_identifier()
                    self.logger.debug(f"Show identifier: {json.dumps(identifier, indent=2)}")
                    trakt_id_str = str(identifier["ids"].get('tmdb', None))
                    media_type_for_filter = "tv"
            else:
                self.logger.debug(f"Skipping Trakt item of unhandled type: {type(item)}")
                continue
            
            unique_key = name # Consolidate by name

            if unique_key in processed_media_map:
                existing_item = processed_media_map[unique_key]
                if last_played_date_iso and \
                   (not existing_item.last_played_date or last_played_date_iso > existing_item.last_played_date):
                    existing_item.last_played_date = last_played_date_iso
                
                if play_count_val is not None: # Aggregate play count from history
                    existing_item.play_count = (existing_item.play_count or 0) + play_count_val
                
                if is_favorite_val: # If it also appears in watchlist
                    existing_item.is_favorite = True
            else:
                processed_media_map[unique_key] = ItemsFiltered(
                    name=name,
                    id=trakt_id_str,
                    type=media_type_for_filter,
                    last_played_date=last_played_date_iso,
                    play_count=play_count_val,
                    is_favorite=is_favorite_val,
                )

        if attribute_filter and attribute_filter.lower() == "name":
            return [pm_item.name for pm_item in processed_media_map.values() if pm_item.name]
        
        return list(processed_media_map.values())

    def get_all_items_filtered(self, attribute_filter: Optional[str] = None) -> Optional[Union[List[ItemsFiltered], List[str]]]:
        # Not implemented
        return None

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Trakt provider.
        These settings will be used by the SettingsService.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Trakt integration."},
            "client_id": {"value": None, "type": SettingType.STRING, "description": "Trakt Client ID.", "required": True}, # Already marked
            "client_secret": {"value": None, "type": SettingType.STRING, "description": "Trakt Client Secret.", "required": True}, # Already marked
            "default_user": {"value": None, "type": SettingType.STRING, "description": "Trakt Default User to use for watch history and favorites, if None use all."},
            "authorization": {"value": None, "type": SettingType.STRING, "show": False, "hide": True, "description": "Trakt Authorization."},
            "redirect_uri": {
                "value": "urn:ietf:wg:oauth:2.0:oob", 
                "type": SettingType.STRING, 
                "description": "Trakt OAuth Redirect URI. 'urn:ietf:wg:oauth:2.0:oob' is common for device auth."
            },
            "enable_media": {"value": False, "type": SettingType.BOOLEAN, "show": False, "description": "This option is not implemented/available for this provider"},
            "enable_history": {"value": True, "type": SettingType.BOOLEAN, "description": "Enable watch history from this library provider. Used for the {{watch_history}} template variable."},
            "base_provider": {"value": "library", "type": SettingType.STRING, "show": False, "description": "Base Provider Type"},
        }