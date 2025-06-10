import json
import logging
from typing import Optional, Dict, List, Any, Union, TYPE_CHECKING
from threading import Condition

from trakt import Trakt
from services.models import ItemsFiltered, SettingType
from base.library_provider_base import LibraryProviderBase

if TYPE_CHECKING:
    from discovarr import Discovarr # For type hinting Discovarr instance

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
        if not self.is_authenticating.acquire(blocking=False):
            self.logger.info('Authentication has already been started')
            return False

        # Request new device code
        code = Trakt['oauth/device'].code()

        print('Enter the code "%s" at %s to authenticate your account' % (
            code.get('user_code'),
            code.get('verification_url')
        ))

        # Construct device authentication poller
        poller = Trakt['oauth/device'].poll(**code)\
            .on('aborted', self.on_aborted)\
            .on('authenticated', self.on_authenticated)\
            .on('expired', self.on_expired)\
            .on('poll', self.on_poll)

        # Start polling for authentication token
        poller.start(daemon=False)

        # Wait for authentication to complete
        return self.is_authenticating.wait()

    def on_aborted(self):
        """Device authentication aborted.

        Triggered when device authentication was aborted (either with `DeviceOAuthPoller.stop()`
        or via the "poll" event)
        """

        self.logger.error('Authentication aborted')

        # Authentication aborted
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_authenticated(self, authorization):
        """Device authenticated.

        :param authorization: Authentication token details
        :type authorization: dict
        """

        # Acquire condition
        self.is_authenticating.acquire()

        # Store authorization for future calls
        self.authorization = authorization
        
        # Configure the Trakt library with the new token
        Trakt.configuration.oauth.from_response(self.authorization)

        # Save access_token and refresh_token to settings
        if self.discovarr_app and self.discovarr_app.settings:
            self.discovarr_app.settings.set('trakt', 'authorization', json.dumps(self.authorization))
            self.logger.info("Trakt access and refresh tokens saved to settings.")

        self.logger.debug('Authentication successful - authorization: %r' % self.authorization)

        # Authentication complete
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_expired(self):
        """Device authentication expired."""

        self.logger.error('Authentication expired')

        # Authentication expired
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_poll(self, callback):
        """Device authentication poll.

        :param callback: Call with `True` to continue polling, or `False` to abort polling
        :type callback: func
        """

        # Continue polling
        callback(True)

    def on_token_refreshed(self, authorization):
        # OAuth token refreshed, store authorization for future calls
        self.authorization = authorization
        
        # Re-configure the Trakt library with the refreshed token
        Trakt.configuration.oauth.from_response(self.authorization)
        
        # Save new access_token and refresh_token to settings
        if self.discovarr_app and self.discovarr_app.settings:
            access_token = self.authorization.get('access_token')
            refresh_token = self.authorization.get('refresh_token')
            if access_token:
                self.discovarr_app.settings.set('trakt', 'access_token', access_token)
            if refresh_token:
                self.discovarr_app.settings.set('trakt', 'refresh_token', refresh_token)

        self.logger.debug('Token refreshed - authorization: %r' % self.authorization)

    def _handle_trakt_exception(self, e: Exception, context: str) -> None:
        """Helper to log Trakt exceptions."""
        self.logger.error(f"Trakt API error during {context}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            self.logger.error(f"Trakt API Response Status: {e.response.status_code}")
            try:
                self.logger.error(f"Trakt API Response Body: {e.response.json()}")
            except json.JSONDecodeError:
                self.logger.error(f"Trakt API Response Body (not JSON): {e.response.text}")

    def get_users(self) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves the authenticated Trakt user.
        Trakt is typically single-user in this context (the authenticated user).
        """
        # Check if authenticated (self.authorization would be set)
        if self.authorization:
            try:
                # Fetch user settings, which includes user profile info
                with Trakt.configuration.oauth.from_response(self.authorization):
                    user_settings = Trakt['users/settings'].get()
                    self.logger.debug(f"Retrieved Trakt user settings: {user_settings}")
                    if user_settings and user_settings.get('user'):
                        user_data = user_settings['user']
                        self.logger.info(f"Retrieved Trakt user profile for: {user_data.get('username')}")
                        return [{
                            "Id": user_data.get("ids", {}).get("slug"),
                            "Name": user_data.get("username"),
                            "FullName": user_data.get("name"),
                            "Private": user_data.get("private"),
                            "Vip": user_data.get("vip"),
                        }]
                    self.logger.warning("TraktProvider: Failed to retrieve user profile or profile in unexpected format.")
            except Exception as e:
                self._handle_trakt_exception(e, "get_users")
        else:
            self.logger.warning("TraktProvider: get_users requires an authenticated session.")
        return None

    def get_user_by_name(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the Trakt user if the username matches the authenticated user.
        """
        users = self.get_users()
        if users:
            for user in users:
                if user.get("Name") == username:
                    self.logger.info(f"TraktProvider: Found authenticated user matching '{username}'.")
                    return user
        self.logger.info(f"TraktProvider: User '{username}' not found or does not match authenticated user.")
        return None

    def get_recently_watched(self, user_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves recently watched items for the Trakt user.
        'user_id' for Trakt would typically be the authenticated user's ID/slug (e.g., 'me' or actual slug).
        """
        if not Trakt['oauth'].token:
            self.logger.warning("TraktProvider: get_recently_watched requires an authenticated session.")
            return None
        try:
            # Fetch combined history (movies and episodes)
            history_items_iter = Trakt[f"users/{user_id}/history"].get(
                media=None, # All types: movies, episodes
                extended='full',
                per_page=limit,
                pagination=False # Fetch up to 'limit' items in one go
            )
            # Convert iterable to list of trakt.Object instances
            watched_items = list(history_items_iter) if history_items_iter else []
            self.logger.debug(f"Watched items: {watched_items}")
            self.logger.info(f"Retrieved {len(watched_items)} recently watched Trakt items for user {user_id}.")
            for item in watched_items:
                self.logger.debug(f"Watched item: {item.to_dict()}")
            return watched_items # Returns List[trakt.objects.history.HistoryItem]
        except Exception as e:
            self._handle_trakt_exception(e, f"get_recently_watched for user {user_id}")
        return None

    def get_favorites(self, user_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves favorite items (e.g., watchlist, personal lists) for the Trakt user.
        'user_id' for Trakt would typically be the authenticated user's ID/slug.
        """
        if not Trakt['oauth'].token:
            self.logger.warning("TraktProvider: get_favorites requires an authenticated session.")
            return None
        
        favorite_items = []
        try:
            # Fetch ratings
            movie_watchlist_iter = Trakt[f"users/{user_id}/ratings"].get(extended='full')
            if movie_watchlist_iter:
                favorite_items.extend(list(movie_watchlist_iter)) # List[trakt.movies.Movie]

            if favorite_items:
                self.logger.info(f"Retrieved {len(favorite_items)} items from watchlist for user {user_id}.")
                if limit:
                    return favorite_items[:limit] # Slice after fetching all
                return favorite_items # Returns List[trakt.movies.Movie | trakt.tv.TVShow]
            
            self.logger.info(f"Watchlist for user {user_id} is empty or failed to retrieve.")
            return []
        except Exception as e:
            self._handle_trakt_exception(e, f"get_favorites for user {user_id}")
        return None

    def get_items_filtered(self, items: Optional[List[Dict[str, Any]]], attribute_filter: Optional[str] = None, source_type: Optional[str] = None) -> Union[List[ItemsFiltered], List[str]]:
        """
        Filters a list of raw Trakt media items.
        Items are expected to be trakt.objects (e.g., HistoryItem, Movie, TVShow).
        'source_type' can be 'history' or 'watchlist'.
        """
        if not items: # items is List[trakt.Object]
            self.logger.debug("TraktProvider: No items provided for filtering.")
            return []

        processed_media_map: Dict[str, ItemsFiltered] = {}

        for trakt_item_obj in items:
            name: Optional[str] = None
            trakt_id_str: Optional[str] = None
            media_type_for_filter: Optional[str] = None # 'movie' or 'tv'
            last_played_date_iso: Optional[str] = None
            play_count_val: Optional[int] = None
            is_favorite_val: bool = (source_type == "watchlist")

            actual_media_object = None # This will be Movie or TVShow object
            
            if isinstance(trakt_item_obj, trakt.objects.history.HistoryItem):
                history_item = trakt_item_obj
                last_played_date_iso = history_item.watched_at.isoformat() if history_item.watched_at else None
                play_count_val = 1 # Each history item represents one play event

                if history_item.type == "movie" and history_item.movie:
                    actual_media_object = history_item.movie
                elif history_item.type == "episode" and history_item.show: # Consolidate episodes under their show
                    actual_media_object = history_item.show
                elif history_item.type == "show" and history_item.show: # Direct show watch history
                    actual_media_object = history_item.show
            elif isinstance(trakt_item_obj, (trakt.movies.Movie, trakt.tv.TVShow)): # From watchlist
                actual_media_object = trakt_item_obj
            else:
                self.logger.debug(f"Skipping Trakt item of unhandled type: {type(trakt_item_obj)}")
                continue

            if not actual_media_object:
                self.logger.debug(f"Could not determine actual media object from Trakt item: {trakt_item_obj}")
                continue

            name = getattr(actual_media_object, 'title', None)
            # trakt.Object has an 'id' attribute which is the trakt id
            trakt_id_val = getattr(actual_media_object, 'id', None) 
            if not trakt_id_val and hasattr(actual_media_object, 'ids') and isinstance(actual_media_object.ids, dict):
                 trakt_id_val = actual_media_object.ids.get('trakt')
            trakt_id_str = str(trakt_id_val) if trakt_id_val else None

            if isinstance(actual_media_object, trakt.movies.Movie):
                media_type_for_filter = "movie"
            elif isinstance(actual_media_object, trakt.tv.TVShow):
                media_type_for_filter = "tv"

            if not name or not trakt_id_str:
                self.logger.debug(f"Skipping Trakt item due to missing name or Trakt ID: {actual_media_object}")
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
                    is_favorite=is_favorite_val
                )

        if attribute_filter and attribute_filter.lower() == "name":
            return [pm_item.name for pm_item in processed_media_map.values() if pm_item.name]
        
        return list(processed_media_map.values())

    def get_all_items_filtered(self, attribute_filter: Optional[str] = None) -> Optional[Union[List[ItemsFiltered], List[str]]]:
        """
        Retrieves all relevant items (e.g., watched, watchlist) from Trakt and filters them.
        NOTE: For a true "all items" fetch, pagination for history/watchlist would be needed
        if they exceed the library's default per-page limits or the 'limit' passed.
        """
        if not Trakt['oauth'].token:
            self.logger.warning("TraktProvider: get_all_items_filtered requires an authenticated session.")
            return None
        
        user_profile = self.get_users()
        if not user_profile or not user_profile[0].get("Id"):
            self.logger.error("TraktProvider: Could not retrieve authenticated user for get_all_items_filtered.")
            return None
        user_id = user_profile[0]["Id"]

        # TODO: Implement proper pagination for a true "all items" fetch.
        self.logger.warning("TraktProvider: get_all_items_filtered will fetch a limited number of items (e.g., per underlying method limits) due to simplified pagination handling.")

        final_processed_map: Dict[str, ItemsFiltered] = {}

        # Fetch watched history (e.g., up to 1000 items for this example)
        watched_history_items = self.get_recently_watched(user_id=user_id, limit=1000)
        if watched_history_items:
            hist_filtered = self.get_items_filtered(items=watched_history_items, source_type="history")
            for item_f in hist_filtered:
                if item_f.name not in final_processed_map: # Check name for uniqueness key
                    final_processed_map[item_f.name] = item_f
                else: 
                    existing = final_processed_map[item_f.name]
                    if item_f.last_played_date and \
                       (not existing.last_played_date or item_f.last_played_date > existing.last_played_date):
                        existing.last_played_date = item_f.last_played_date
                    if item_f.play_count is not None:
                         existing.play_count = (existing.play_count or 0) + item_f.play_count
        
        # Fetch watchlist items (get_favorites fetches all by default, then slices if limit was passed)
        watchlist_items = self.get_favorites(user_id=user_id) 
        if watchlist_items:
            watch_filtered = self.get_items_filtered(items=watchlist_items, source_type="watchlist")
            for item_f in watch_filtered:
                if item_f.name not in final_processed_map: # Check name for uniqueness key
                    final_processed_map[item_f.name] = item_f
                else: 
                    final_processed_map[item_f.name].is_favorite = True # Mark as favorite

        if not final_processed_map:
            self.logger.info("No items found from history or watchlist for filtering.")
            return []

        filtered_list = list(final_processed_map.values())

        if attribute_filter and attribute_filter.lower() == "name":
            return [item.name for item in filtered_list if item.name]
        
        return filtered_list

    # TODO: Add methods for OAuth flow (get_authorization_url, exchange_code_for_token, refresh_token)
    # if this provider is responsible for handling it.
    # The `trakt` library provides helpers:
    # trakt.Trakt.oauth.device_code()
    # trakt.Trakt.oauth.token_from_device_code(...)
    # trakt.Trakt.oauth.authorize_url(...)
    # trakt.Trakt.oauth.token(...)
    # trakt.Trakt.oauth.refresh_token(...)

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Trakt provider.
        These settings will be used by the SettingsService.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Trakt integration."},
            "client_id": {"value": None, "type": SettingType.STRING, "description": "Trakt Client ID."},
            "client_secret": {"value": None, "type": SettingType.STRING, "description": "Trakt Client Secret."},
            "authorization": {"value": None, "type": SettingType.STRING, "show": False, "description": "Trakt Authorization."},
            "redirect_uri": {
                "value": "urn:ietf:wg:oauth:2.0:oob", 
                "type": SettingType.STRING, 
                "description": "Trakt OAuth Redirect URI. 'urn:ietf:wg:oauth:2.0:oob' is common for device auth."
            },
        }