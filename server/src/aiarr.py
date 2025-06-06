import requests
import json
import logging
import sys
import os
import traceback 
from datetime import datetime, timedelta
from jinja2 import Template # Import Jinja2 Template
from urllib.parse import urljoin
from typing import Optional, Dict, List, Any  # Import typing for better code clarity
from services.jellyfin import Jellyfin
from services.radarr import Radarr
from services.sonarr import Sonarr  
from services.gemini import Gemini
from services.ollama import Ollama
from services.tmdb import TMDB
from services.database import Database
from services.scheduler import AiArrScheduler
from services.settings import SettingsService
from services.response import APIResponse
from services.plex import Plex
from services.models import ItemsFiltered

class AiArr:
    """
    A class to interact with Jellyseerr, Jellyfin, and Gemini APIs for media requests and management.
    """

    def __init__(self): 
        """
        Initializes the AiArr class and sets up logging and API configurations.
        """
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing AiArr class...")

        # Log current system time and timezone
        now = datetime.now()
        local_tz = now.astimezone().tzinfo
        self.logger.info(f"Current system time: {now.strftime('%Y-%m-%d %H:%M:%S')} Timezone: {local_tz}")

        self.db = Database("/config/aiarr.db")
        # Pass self (AiArr instance) to SettingsService for callback
        self.settings = SettingsService(aiarr_app=self)

        # Initialize attributes to None or default before first load
        # This helps with type hinting and ensures attributes exist
        self.recent_limit = None
        self.suggestion_limit = None
        self.test_mode = None
        self.backup_before_upgrade = None
        self.default_prompt = None
        self.jellyfin_enabled = None 
        self.jellyfin_url = None
        self.plex_url = None 
        self.plex_enabled = None 
        self.plex_token = None 
        self.jellyfin_api_key = None
        self.radarr_url = None
        self.radarr_api_key = None
        self.radarr_default_quality_profile_id = None
        self.sonarr_url = None
        self.sonarr_api_key = None
        self.sonarr_default_quality_profile_id = None
        self.gemini_enabled = None 
        self.gemini_api_key = None
        self.gemini_model = None
        self.gemini_thinking_budget = None 
        self.gemini_temperature = None 
        self.ollama_enabled = None # Initialize Ollama setting
        self.ollama_base_url = None # Initialize Ollama setting
        self.ollama_model = None # Initialize Ollama setting
        self.ollama_temperature = None # 
        self.tmdb_api_key = None
        self.auto_media_save = None
        self.system_prompt = None 

        self.plex = None # Initialize Plex service instance
        self.jellyfin = None
        self.radarr = None
        self.sonarr = None
        self.gemini = None
        self.ollama = None
        self.tmdb = None
        self.jellyfin_user_id = None

        # Load backup setting first as it's needed for Database initialization
        self.backup_before_upgrade = self.settings.get("app", "backup_before_upgrade")
        # Initialize Database with the backup setting
        self.db = Database("/config/aiarr.db", backup_on_upgrade=self.backup_before_upgrade)
        # Load the rest of the configuration and (re)initialize other services
        try:
            self.reload_configuration()
        except ValueError as e:
            self.logger.critical(f"Fatal configuration error during startup: {e}. Exiting.")
            sys.exit(1)

        # Initialize scheduler (depends on a fully configured AiArr instance)
        self.scheduler = AiArrScheduler(db=self.db, aiarr_instance=self)
        self.logger.info("Scheduler initialized")
    def reload_configuration(self) -> None:
        """Loads/reloads configuration from settings and (re)initializes services."""
        self.logger.info("Loading/Reloading AiArr configuration...")

        # Load configuration values from SettingsService
        self.recent_limit = self.settings.get("app", "recent_limit")
        self.suggestion_limit = self.settings.get("app", "suggestion_limit")
        self.test_mode = self.settings.get("app", "test_mode")
        self.backup_before_upgrade = self.settings.get("app", "backup_before_upgrade")
        self.default_prompt = self.settings.get("app", "default_prompt")
        self.auto_media_save = self.settings.get("app", "auto_media_save")
        self.plex_enabled = self.settings.get("plex", "enabled") # Load Plex enabled status
        self.plex_url = self.settings.get("plex", "url") # Load Plex settings
        self.plex_token = self.settings.get("plex", "api_token") # Load Plex settings
        self.jellyfin_enabled = self.settings.get("jellyfin", "enabled") # Load Jellyfin enabled status
        self.jellyfin_url = self.settings.get("jellyfin", "url")
        self.jellyfin_api_key = self.settings.get("jellyfin", "api_key")
        self.radarr_url = self.settings.get("radarr", "url")
        self.radarr_api_key = self.settings.get("radarr", "api_key")
        self.radarr_default_quality_profile_id = self.settings.get("radarr", "default_quality_profile_id")
        self.sonarr_url = self.settings.get("sonarr", "url")
        self.sonarr_api_key = self.settings.get("sonarr", "api_key")
        self.sonarr_default_quality_profile_id = self.settings.get("sonarr", "default_quality_profile_id")
        self.gemini_enabled = self.settings.get("gemini", "enabled") 
        self.gemini_api_key = self.settings.get("gemini", "api_key")
        self.gemini_model = self.settings.get("gemini", "model")
        self.gemini_thinking_budget = self.settings.get("gemini", "thinking_budget")
        self.gemini_temperature = self.settings.get("gemini", "temperature")
        self.ollama_enabled = self.settings.get("ollama", "enabled")
        self.ollama_base_url = self.settings.get("ollama", "base_url")
        self.ollama_model = self.settings.get("ollama", "model")
        self.ollama_temperature = self.settings.get("ollama", "temperature")
        self.tmdb_api_key = self.settings.get("tmdb", "api_key")
        self.system_prompt = self.settings.get("app", "system_prompt")
        
        self.jellyfin_auth = None # This seems to be an unused attribute, keeping for now

        # If DB was already initialized, and this setting affects its runtime behavior
        # (beyond initial migration backup), we might need to update the DB instance.
        # For now, backup_on_upgrade is used only during DB initialization.
        # If self.db needs to be reconfigured: self.db.set_backup_preference(self.backup_before_upgrade) or re-init

        # Validate the loaded configuration
        try:
            self._validate_configuration()
        except ValueError as e:
            self.logger.error(f"Configuration validation error: {e}")
 
        # (Re)Initialize services with the new configuration
        self.plex = None # Reset before potential re-init
        self.jellyfin_user_id = None
        self.jellyfin = None # Reset before potential re-init

        if self.plex_enabled and self.plex_url and self.plex_token:
             self.plex = Plex(
                plex_url=self.plex_url,
                plex_token=self.plex_token,
                limit=self.recent_limit # Use recent_limit for default Plex limit
            )
             self.logger.info("Plex service initialized.")
        elif self.plex_enabled:
            self.logger.warning("Plex is enabled but URL or token is missing. Plex service not initialized.")
        else:
            self.logger.info("Plex integration is disabled.")

        if self.jellyfin_enabled and self.jellyfin_url and self.jellyfin_api_key:
            self.jellyfin = Jellyfin(
                jellyfin_url=self.jellyfin_url,
                jellyfin_api_key=self.jellyfin_api_key,
            )
            self.logger.info("Jellyfin service initialized.")
        elif self.jellyfin_enabled:
            self.logger.warning("Jellyfin is enabled but URL or API key is missing. Jellyfin service not initialized.")
        else:
            self.logger.info("Jellyfin integration is disabled.")
        self.radarr = Radarr(
            url=self.radarr_url,
            api_key=self.radarr_api_key,
        )
        self.sonarr = Sonarr(
            url=self.sonarr_url,
            api_key=self.sonarr_api_key,
        )
        if self.gemini_enabled and self.gemini_api_key:
            self.gemini = Gemini(
                gemini_api_key=self.gemini_api_key
            )
        else:
            self.gemini = None
            self.logger.info("Gemini API key not configured. Gemini service disabled.")

        if self.ollama_enabled and self.ollama_base_url:
            self.ollama = Ollama(
                ollama_base_url=self.ollama_base_url,
            )
            self.logger.info("Ollama service initialized.")
        elif self.ollama_enabled:
            self.logger.warning("Ollama is enabled but Base URL or Model is missing. Ollama service not initialized.")
        else:
            self.logger.info("Ollama integration is disabled.")

        self.tmdb = TMDB(tmdb_api_key=self.tmdb_api_key)
        self.logger.info("AiArr configuration processed and services (re)initialized.")

    def _validate_configuration(self) -> None:
        """
        Validates the required settings configuration.
        Raises ValueError if a required configuration is missing for an enabled service.
        """
        if self.jellyfin_enabled:
            if not self.jellyfin_url:
                raise ValueError("Jellyfin URL is required when Jellyfin integration is enabled.")
            if not self.jellyfin_api_key:
                raise ValueError("Jellyfin API key is required when Jellyfin integration is enabled.")
        
        if self.plex_enabled:
            if not self.plex_url:
                raise ValueError("Plex URL is required when Plex integration is enabled.")
            if not self.plex_token:
                raise ValueError("Plex API token is required when Plex integration is enabled.")

        if self.radarr_url and not self.radarr_api_key:
            raise ValueError("Both Radarr URL and API key are required if Radarr URL is provided.")
        if self.sonarr_url and not self.sonarr_api_key:
            raise ValueError("Both Sonarr URL and API key are required if Sonarr URL is provided.")
        if self.gemini_enabled:
            if self.gemini_api_key:
                raise ValueError("Gemini API key is required if a Gemini model is specified.")
        if self.ollama_enabled:
            if not self.ollama_base_url:
                raise ValueError("Ollama Base URL is required when Ollama integration is enabled.")
 
    # --- Plex Methods ---
    def plex_get_users(self) -> Optional[List[Dict[str, Any]]]:
        """Get all managed Plex users."""
        if not self.plex:
            self.logger.warning("Plex service not available.")
            return None
        return self.plex.get_users()

    def plex_get_user_by_name(self, plex_username: str) -> Optional[Dict[str, Any]]:
        """Get a specific Plex user by name."""
        if not self.plex:
            self.logger.warning("Plex service not available.")
            return None
        return self.plex.get_user_by_name(plex_username)

    def plex_get_recently_watched(self, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """Get recently watched items for the default Plex user."""
        if not self.plex:
            self.logger.warning("Plex service not available.")
            return None
        # TODO: Make username configurable instead of hardcoding "trevor"
        # For now, assuming the main account token is used or a specific user context is desired.
        # If using a managed user's token, this would be simpler.
        # If using main account token and want a specific managed user's history, need their ID.
        user = self.plex.get_user_by_name("tsquillario") # Example, replace "trevor" or make configurable
        if not user:
            self.logger.warning("Default Plex user 'trevor' not found for recently watched. Ensure user exists or configure.")
            # Fallback: If no specific user, try to get history for the account associated with the token.
            # Plex's /status/sessions/history/all with `accountID` filters by that account.
            # If `accountID` is omitted, it might show history for the token's primary account.
            # For simplicity, we require a user ID here.
            return None
        return self.plex.get_recently_watched(plex_user_id=user.get("id"), limit=limit, to_json_output=True)

    def plex_get_recently_watched_filtered(self, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """Get filtered recently watched items for the default Plex user."""
        user = self.plex.get_user_by_name("tsquillario") # Example, replace "trevor" or make configurable
        if not user:
            self.logger.warning("Default Plex user 'trevor' not found for recently watched. Ensure user exists or configure.")
        raw_items = self.plex.get_recently_watched(plex_user_id=user.get("id"), limit=limit, to_json_output=False)
        if raw_items is None: # Indicates an error during fetch or user not found
            return None
        # get_items_filtered handles empty list if no items were returned
        return self.plex.get_items_filtered(items=raw_items, source_type="history")

    def plex_get_all_items_filtered(self, attribute_filter: Optional[str] = None) -> Optional[List[Any]]:
        """Get all filtered library items (movies/shows) from Plex."""
        if not self.plex:
            self.logger.warning("Plex service not available.")
            return None
        return self.plex.get_all_items_filtered(attribute_filter=attribute_filter)

    def jellyfin_get_recently_watched(self, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        if not self.jellyfin:
            self.logger.warning("Jellyfin service not available.")
            return None
        user = self.jellyfin.get_user_by_name("trevor")
        return self.jellyfin.get_recently_watched(limit=limit, jellyfin_user_id=user.get("Id"))
    
    def jellyfin_get_recently_watched_filtered(self, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        if not self.jellyfin:
            self.logger.warning("Jellyfin service not available.")
            return None
        user = self.jellyfin.get_user_by_name("trevor")
        r = self.jellyfin.get_recently_watched(limit=limit, jellyfin_user_id=user.get("Id"))
        return self.jellyfin.get_items_filtered(items=r, attribute_filter="Name")
    def get_prompt(self, limit: int, media_name: Optional[str] = None, favorite_option: Optional[str] = None, template_string: Optional[str] = None) -> str:
        """
        Renders a prompt string using Jinja2 templating.

        Args:
            template_string (str): The Jinja2 template string.
            limit (int): The limit to be used in the template.
            media_name (str): The media name to be used in the template.

        Returns:
            str: The rendered prompt string.
        """
        try:
            self.logger.debug(f"Prompt limit: {limit}")
            self.logger.debug(f"Prompt media_name: {media_name}")
            self.logger.debug(f"Prompt favorite_option: {favorite_option}")
            self.logger.debug(f"Prompt template_string: {template_string}")
            # Get current movies and series from jellyfin to exclude from suggestions
            all_media = []
            if self.jellyfin:
                jellyfin_media = self.jellyfin.get_all_items_filtered(attribute_filter="Name")
                if jellyfin_media: all_media.extend(jellyfin_media)
            if self.plex: # Add Plex media if Plex is configured
                plex_media = self.plex.get_all_items_filtered(attribute_filter="name") # ItemsFiltered uses 'name'
                if plex_media: all_media.extend(plex_media)
            self.logger.debug(f"{len(all_media)} titles found")
            # Get ignored suggestions to exclude as well
            all_ignored = self.db.get_ignored_media_titles()
            self.logger.debug(f"{len(all_ignored)} titles to ignore")
            # Combine lists and convert to a comma-separated string
            all_ignored_str = ",".join(all_ignored + all_media)
            self.logger.info("Finding similar media for: %s", media_name)
            self.logger.info("Exclude: %s", all_ignored_str)

            # Template variable for favorites
            favorites_str = ""
            all_favorites = []
            # IF favorites is specified, get favorites
            if favorite_option:
                if self.jellyfin:
                    if favorite_option == "all":
                        all_jellyfin_users = self.jellyfin.get_users()
                        if all_jellyfin_users:
                            for user in all_jellyfin_users:
                                user_favorites = self.jellyfin.get_favorites(jellyfin_user_id=user.get("Id"))
                                user_favorites_filtered = self.jellyfin.get_items_filtered(items=user_favorites, attribute_filter="Name")
                                self.logger.debug(f"Jellyfin User {user.get('Name')} favorites: {user_favorites_filtered}")
                                if user_favorites_filtered: all_favorites.extend(user_favorites_filtered)
                    else: # Specific Jellyfin user
                        user = self.jellyfin.get_user_by_name(jellyfin_username=favorite_option)
                        if user:
                            self.logger.debug(f"Jellyfin User {user.get('Name')} found with ID {user.get('Id')}")
                            user_favorites = self.jellyfin.get_favorites(jellyfin_user_id=user.get("Id"))
                            user_favorites_filtered = self.jellyfin.get_items_filtered(items=user_favorites, attribute_filter="Name")
                            if user_favorites_filtered: all_favorites.extend(user_favorites_filtered)
                            self.logger.debug(f"Jellyfin User {user.get('Name')} favorites: {user_favorites_filtered}")
                
                if self.plex: # Add Plex favorites if Plex is configured
                    # Plex favorites are tied to the token, plex_user_id is a hint.
                    # Using a placeholder or default user ID context for Plex get_favorites.
                    # This part might need refinement based on how Plex user context for ratings is handled.
                    plex_user_for_favorites = self.plex.get_user_by_name(favorite_option) # Try specific user
                    if not plex_user_for_favorites and favorite_option == "all": # Or a default if "all"
                        plex_user_for_favorites = self.plex.get_user_by_name("trevor") # Example default
                    if plex_user_for_favorites:
                        plex_favs_raw = self.plex.get_favorites(plex_user_id=plex_user_for_favorites.get("id"))
                        plex_favs_filtered_names = self.plex.get_items_filtered(items=plex_favs_raw, source_type="library_favorites", attribute_filter="name")
                        if plex_favs_filtered_names: all_favorites.extend(plex_favs_filtered_names)
                        self.logger.debug(f"Plex User context '{plex_user_for_favorites.get('name')}' favorites (names): {plex_favs_filtered_names}")

            self.logger.debug(f"All favorites count: {len(all_favorites)}")
            if len(all_favorites) > 0:
                favorites_str = ",".join(all_favorites)
                self.logger.info(f"Favorite Media: {favorites_str}")

            if not template_string:
                template_string = self.default_prompt

            template = Template(template_string)
            rendered_prompt = template.render(
                limit=limit, media_name=media_name, media_exclude=all_ignored_str, favorites=favorites_str
            )
            return rendered_prompt
        except Exception as e:
            self.logger.error(f"Error rendering Jinja2 template: {e}", exc_info=True)
            # Depending on desired behavior, you might return an empty string or raise the exception
            return f"Error rendering prompt: {e}"

    async def get_similar_media(self, media_name: Optional[str] = None, custom_prompt: Optional[str] = None, search_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        suggestions = []
        template_string = self.default_prompt
        if custom_prompt:
            template_string = custom_prompt
        prompt = self.get_prompt(limit=self.suggestion_limit, media_name=media_name, template_string=template_string)

        result = None
        model = None
        if self.gemini:
            if not self.gemini_model:
                raise ValueError("Gemini model is required.")
            model = self.gemini_model
            result = await self.gemini.get_similar_media(prompt=prompt, model=model, system_prompt=self.system_prompt, temperature=self.gemini_temperature, thinking_budget=self.gemini_thinking_budget)
        elif self.ollama:
            if not self.ollama_model:
                raise ValueError("Ollama model is required.")
            model = self.ollama_model
            result = await self.ollama.get_similar_media(prompt=prompt, model=model, system_prompt=self.system_prompt, temperature=self.ollama_temperature)

        if result:
            response = result['response']
            token_counts = result['token_counts']
            
            self.db.add_search_stat(search_id, token_counts)
            self.logger.debug(f"Stored token usage stats for search {search_id}: {token_counts}")

            self.logger.info("Similar Media: %s", json.dumps(response, indent=2))
            for media in response.get("suggestions"):
                title = media.get("title")
                media_type = media.get("mediaType")

                # Lookup TMDB ID
                tmdb_lookup = self.tmdb.lookup_media(title, media_type)
                if tmdb_lookup:
                    tmdb_id = tmdb_lookup.get("id")
                    # Get media details from TMDB
                    tmdb_media_detail = self.tmdb.get_media_detail(tmdb_id, media_type)
                    # Get poster art from TMDB
                    image_url =  f"https://image.tmdb.org/t/p/w500{tmdb_media_detail.get('poster_path')}" 
                    # Data validation
                    rt_score = media.get("rt_score")
                    if rt_score and isinstance(rt_score, str):
                        rt_score = int(rt_score.replace("%", ""))

                    # Prepare network data
                    network_names = []
                    if media_type == "tv" and tmdb_media_detail.get("networks"):
                        network_names = [net.get("name") for net in tmdb_media_detail.get("networks") if net.get("name")]
                    elif media_type == "movie":
                        network_names = None

                    # Prepare genres data
                    genre_names = []
                    if tmdb_media_detail.get("genres"):
                        genre_names = [g.get("name") for g in tmdb_media_detail.get("genres")]

                    release_date_val = tmdb_media_detail.get("release_date") if media_type == "movie" else tmdb_media_detail.get("last_air_date")

                    # Search for existing media in database
                    existing_media = self.db.search_media(title)
                    if not existing_media:
                        # Create new media entry if it doesn't exist
                        media_data = {
                            "title": title,
                            "source_title": media_name,
                            "description": media.get("description"),
                            "similarity": media.get("similarity"),
                            "media_type": media_type,
                            "tmdb_id": tmdb_id,
                            "poster_url": image_url,
                            "rt_url": media.get("rt_url"),
                            "rt_score": rt_score,
                            "ignore": 0,  # Default to not ignored
                            "media_status": tmdb_media_detail.get("status"),
                            "release_date": release_date_val,
                            "networks": ", ".join(network_names) if network_names else None,
                            "genres": ", ".join(genre_names) if genre_names else None,
                            "original_language": tmdb_media_detail.get("original_language"),
                            "search_id": search_id,
                        }
                        # Save results if running an ad-hoc search with the Auto Media Save option selected or when running a saved search.
                        if self.auto_media_save or search_id: 
                            media_id = self.db.create_media(media_data)
                            if media_id:
                                self.logger.info(f"Created new media entry for {title} with ID {media_id}")
                            else:
                                self.logger.error(f"Failed to create media entry for {title}")
                    else:
                        # Update existing media entry
                        existing_media_first = existing_media[0]
                        self.logger.info(f"Media {existing_media_first.get('id')}:{title} already exists in database")
                        media_data = {
                            "title": media.get("title"),
                            "source_title": media_name,
                            "description": media.get("description"),
                            "similarity": media.get("similarity"),
                            "media_type": media_type,
                            "tmdb_id": tmdb_id,
                            "poster_url": image_url,
                            "rt_url": media.get("rt_url"),
                            "rt_score": rt_score,
                            "media_status": tmdb_media_detail.get("status"),
                            "release_date": release_date_val,
                            "networks": ", ".join(network_names) if network_names else None,
                            "genres": ", ".join(genre_names) if genre_names else None,
                            "original_language": tmdb_media_detail.get("original_language"),
                        }
                        # Save results if running an ad-hoc search with the Auto Media Save option selected or when running a saved search.
                        if self.auto_media_save or search_id: 
                            update_success = self.db.update_media(existing_media_first.get("id"), media_data)
                            if update_success:
                                self.logger.info(f"Updated media entry for {title}")
                            else:
                                self.logger.error(f"Failed to update media entry for {title}")


                    self.logger.debug(f"Media: {media_data}")
                    suggestions.append(media_data)
            
            if search_id:
                now = datetime.now()
                self.logger.debug(f"Updating Search ID: {search_id}, Last Run Date: {now}")
                self.db.update_search_run_date(search_id=search_id, last_run_date=now)

            return suggestions
        else:
            self.logger.error("Failed to retrieve similar media.")

    async def process_watch_history(self) -> Any:
        """
        Main method to process media requests and find similar media.
        Stores suggestions in SQLite database and returns them.
        """
        try:
            default_search = self.db.get_search(search_id=1)
            if not default_search:
                self.logger.error("Default search not found in the database. Cannot process suggestions.")
                raise RuntimeError("Default search not found in the database.")
            search_id = default_search.get("id")
            self.logger.info(f"Using default search ID: {search_id} for suggestions.")

            watch_history = self.db.get_watch_history(limit=self.recent_limit, processed=False)

            for history in watch_history:
                media_name = history.get("title")
                similar_media_result = await self.get_similar_media(media_name=media_name, search_id=search_id)
                if similar_media_result:
                    self.db.update_watch_history_processed(history.get("id"), processed=True)

            if len(watch_history) == 0:
                self.logger.info("No new watch history items to process.")
            
        except RuntimeError as e:
            self.logger.error(f"Halting watch history processing due to critical error: {e}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during watch history processing: {e}", exc_info=True)

    async def gemini_get_models(self) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves the list of available Gemini models.

        Returns:
            Optional[List[Dict[str, Any]]]: A list of model details or None if Gemini service is not available or an error occurs.
        """
        if not self.gemini:
            self.logger.warning("Gemini service is not configured. Cannot retrieve models.")
            return None
        try:
            self.logger.info("Fetching available Gemini models.")
            return await self.gemini.get_models()
        except Exception as e:
            self.logger.error(f"Error retrieving Gemini models from AiArr: {e}", exc_info=True)
            return None
        
    async def ollama_get_models(self) -> Optional[List[str]]:
        """
        Retrieves the list of available Ollama models.

        Returns:
            Optional[List[str]]: A list of model names or None if Ollama service is not available or an error occurs.
        """
        if not self.ollama:
            self.logger.warning("Ollama service is not configured. Cannot retrieve models.")
            return None
        try:
            self.logger.info("Fetching available Ollama models.")
            return await self.ollama.get_models()
        except Exception as e:
            self.logger.error(f"Error retrieving Ollama models from AiArr: {e}", exc_info=True)
            return None


    def _sync_watch_history_to_db(self, user_name: str, user_id: str, recently_watched_items: Optional[List[Dict[str, Any]]], source: str) -> None:
        """Helper method to filter and add/update watch history items in the database."""
        if recently_watched_items is None or not recently_watched_items:
            self.logger.info(f"No new recently watched items for {user_name} from {source} or error fetching.")
            return

        filter_func = self.jellyfin.get_items_filtered if source == "jellyfin" else self.plex.get_items_filtered
        unique_items = filter_func(recently_watched_items, source_type="history" if source == "plex" else None) # Pass source_type for Plex

        if unique_items:
            for item in unique_items: # item is ItemsFiltered
                self.db.add_watch_history(
                    title=item.name,
                    id=item.id,
                    media_type=item.type,
                    watched_by=user_name,
                    last_played_date=item.last_played_date
                )
            self.logger.info(f"Synced and added/updated {len(unique_items)} unique recently watched title(s) for {user_name} from {source}.")

    def sync_watch_history(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves the list of available Gemini models.

        Returns:
            Optional[List[Dict[str, Any]]]: A list of model details or None if Gemini service is not available or an error occurs.
        """
        all_users_data: Dict[str, Dict[str, Any]] = {}

        # Sync Jellyfin history
        if self.jellyfin:
            jellyfin_users = self.jellyfin.get_users()
            if not jellyfin_users:
                self.logger.warning("No Jellyfin users found to sync watch history.")
            else:
                self.logger.info(f"Starting Jellyfin watch history sync for {len(jellyfin_users)} user(s).")
                for user_data in jellyfin_users:
                    user_name = user_data.get("Name")
                    user_id = user_data.get("Id")
                    if not user_name or not user_id:
                        self.logger.warning(f"Skipping Jellyfin user with missing Name or Id: {user_data}")
                        continue
                    self.logger.debug(f"Syncing watch history for Jellyfin user: {user_name} (ID: {user_id})")
                    recently_watched_items = self.jellyfin.get_recently_watched(
                        jellyfin_user_id=user_id, limit=self.recent_limit
                    )
                    self._sync_watch_history_to_db(user_name, user_id, recently_watched_items, "jellyfin")
                    # Store filtered names for the response, consistent with previous behavior
                    filtered_item_names = [item.name for item in self.jellyfin.get_items_filtered(recently_watched_items) or []]
                    all_users_data.setdefault(user_name, {"id": user_id, "recent_titles": []})["recent_titles"].extend(filtered_item_names)
        else:
            self.logger.info("Jellyfin service not configured. Skipping Jellyfin watch history sync.")

        # Sync Plex history
        if self.plex:
            plex_users = self.plex.get_users() # These are managed accounts
            if not plex_users: # If no managed users, consider syncing for the main account if desired
                self.logger.warning("No managed Plex users found to sync watch history.")
                # Optionally, you could add logic here to sync for the main account if plex_users is empty
            else:
                self.logger.info(f"Starting Plex watch history sync for {len(plex_users)} managed user(s).")
                for user_data in plex_users: # user_data is a dict from Plex API
                    user_name = user_data.get("name") # Plex uses 'name'
                    user_id = str(user_data.get("id")) # Plex uses 'id', ensure string
                    if not user_name or not user_id:
                        self.logger.warning(f"Skipping Plex user with missing name or id: {user_data}")
                        continue
                    self.logger.debug(f"Syncing watch history for Plex user: {user_name} (ID: {user_id})")
                    recently_watched_items = self.plex.get_recently_watched(plex_user_id=user_id, limit=self.recent_limit, to_json_output=True)
                    self._sync_watch_history_to_db(user_name, user_id, recently_watched_items, "plex")
                    filtered_item_names = [item.name for item in self.plex.get_items_filtered(recently_watched_items, source_type="history") or []]
                    all_users_data.setdefault(user_name, {"id": user_id, "recent_titles": []})["recent_titles"].extend(filtered_item_names)
        else:
            self.logger.info("Plex service not configured. Skipping Plex watch history sync.")

        # Ensure uniqueness in recent_titles if a user exists in both systems with the same name
        for user_name_key in all_users_data:
            all_users_data[user_name_key]["recent_titles"] = sorted(list(set(all_users_data[user_name_key]["recent_titles"])))

        return all_users_data

    def request_media(self, tmdb_id: str, media_type: str, quality_profile_id: Optional[int], save_default: Optional[bool] = False) -> Optional[Dict[str, Any]]:
        """
        Request media (movie or TV show) using TMDB ID and media type.

        Args:
            tmdb_id (str): The TMDB ID of the media
            media_type (str): Type of media to request ('tv' or 'movie')
            quality_profile_id (Optional[int]): The quality profile ID selected by the user.
            save_default (Optional[bool]): Whether to save the selected quality_profile_id as the default.

        Returns:
            Optional[Dict[str, Any]]: JSON response from the API or None on error
        """
        self.logger.info(f"Requesting {media_type} with TMDB ID: {tmdb_id}")
        
        actual_quality_profile_id_to_use = quality_profile_id
        if media_type == "movie":
            if not actual_quality_profile_id_to_use: # Handles None or 0
                actual_quality_profile_id_to_use = self.radarr_default_quality_profile_id
            
            if save_default and quality_profile_id is not None: # Use the user-selected profile ID
                self.logger.info(f"Saving Radarr default quality profile ID: {quality_profile_id}")
                self.settings.set("radarr", "default_quality_profile_id", quality_profile_id)
                # self.radarr_default_quality_profile_id will be updated on next reload_configuration by settings service

            request = self.radarr.add_movie(tmdb_id=tmdb_id, quality_profile_id=actual_quality_profile_id_to_use, search_for_movie=not self.test_mode)
            self.logger.debug(f"Radarr Add Movie Response: {json.dumps(request.data, indent=2)}")
        elif media_type == "tv":
            if not actual_quality_profile_id_to_use: # Handles None or 0
                actual_quality_profile_id_to_use = self.sonarr_default_quality_profile_id
            
            if save_default and quality_profile_id is not None: # Use the user-selected profile ID
                self.logger.info(f"Saving Sonarr default quality profile ID: {quality_profile_id}")
                self.settings.set("sonarr", "default_quality_profile_id", quality_profile_id)
                # self.sonarr_default_quality_profile_id will be updated on next reload_configuration by settings service

            request = self.sonarr.add_series(tmdb_id=tmdb_id, quality_profile_id=actual_quality_profile_id_to_use, search_for_missing=not self.test_mode)
        else:
            self.logger.error(f"Invalid media type: {media_type}. Must be 'tv' or 'movie'")
            return None
        
        return request
    def get_quality_profiles(self, media_type: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get quality profiles from either Radarr or Sonarr based on media type.

        Args:
            media_type (str): Type of media ('tv' or 'movie')

        Returns:
            Optional[List[Dict[str, Any]]]: List of simplified quality profiles or None on error.
            Each profile contains:
                - id: The profile ID
                - name: The profile name
        """
        self.logger.info(f"Retrieving quality profiles for {media_type}")
        try:
            if media_type == "movie":
                profiles = self.radarr.get_quality_profiles(default_profile_id=self.radarr_default_quality_profile_id)
            elif media_type == "tv":
                profiles = self.sonarr.get_quality_profiles(default_profile_id=self.sonarr_default_quality_profile_id)
            else:
                self.logger.error(f"Invalid media type: {media_type}. Must be 'tv' or 'movie'")
                return None
                
            if profiles.success:
                self.logger.info(f"Retrieved {len(profiles.data)} quality profiles")
                return profiles.data
            else:
                self.logger.error(f"No quality profiles found for {media_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving quality profiles: {e}", exc_info=True)
            return None

    def get_users(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all users from Jellyfin.

        Returns:
            Optional[List[Dict[str, Any]]]: List of user objects, or None if an error occurs.
        """
        self.logger.info("Retrieving all users from Jellyfin.")
        if self.jellyfin:
            return self.jellyfin.get_users()
        self.logger.warning("Jellyfin service not available to retrieve users.")
        return None
    def get_active_media(self) -> List[Dict[str, Any]]:
        """
        Get all non-ignored media entries from the database.

        Returns:
            List[Dict[str, Any]]: List of active media entries
        """
        return self.db.get_non_ignored_media()

    def get_ignored_media(self) -> List[Dict[str, Any]]:
        """
        Get all ignored media entries from the database.

        Returns:
            List[Dict[str, Any]]: List of ignored media entries
        """
        return self.db.get_ignored_media()

    def toggle_ignore_status(self, media_id: int) -> Dict[str, Any]:
        """
        Toggle the ignore status for a specific media entry.

        Args:
            media_id (int): ID of the media to toggle

        Returns:
            Dict[str, Any]: Response indicating success or failure
        """
        success = self.db.toggle_ignore(media_id)
        if success:
            return {"status": "success", "message": f"Toggled ignore status for media ID {media_id}"}
        return {"status": "error", "message": f"Failed to toggle ignore status for media ID {media_id}"}

    def update_ignore_status(self, media_id: int, ignore: bool) -> Dict[str, Any]:
        """
        Update the ignore status for a specific media entry.

        Args:
            media_id (int): ID of the media to update
            ignore (bool): New ignore status

        Returns:
            Dict[str, Any]: Response indicating success or failure
        """
        success = self.db.update_ignore_status(media_id, ignore)
        if success:
            return {"status": "success", "message": f"Updated ignore status for media ID {media_id} to {ignore}"}
        return {"status": "error", "message": f"Failed to update ignore status for media ID {media_id}"}

    def save_search(self, prompt: str, name: str, **kwargs) -> Optional[int]:
        """
        Save a search prompt to the database.

        Args:
            prompt (str): The search prompt to save

        Returns:
            Optional[int]: ID of the created search entry, or None on error
        """
        try:
            return self.db.add_search(prompt=prompt, name=name, kwargs=kwargs)
        except Exception as e:
            self.logger.error(f"Error saving search: {e}")
            return None

    def delete_search(self, search_id: int) -> bool:
        """
        Delete a search from the database.

        Args:
            search_id (int): ID of the search to delete

        Returns:
            bool: True if deletion was successful, False if search not found or error occurred
        """
        try:
            return self.db.delete_search(search_id)
        except Exception as e:
            self.logger.error(f"Error deleting search: {e}")
            return False

    def update_search(self, search_id: int, prompt: str, name: str, **kwargs) -> bool:
        """
        Update an existing search prompt in the database.

        Args:
            search_id (int): ID of the search to update
            prompt (str): The new search prompt

        Returns:
            bool: True if update was successful, False if search not found or error occurred
        """
        try:
            return self.db.update_search(search_id, prompt, name, kwargs=kwargs)
        except Exception as e:
            self.logger.error(f"Error updating search: {e}")
            return False

    def get_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent searches from the database.

        Args:
            limit (int): Maximum number of entries to return

        Returns:
            List[Dict[str, Any]]: List of recent searches
        """
        return self.db.get_searches(limit)

    def get_search_stat_summary(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, int]:
        """
        Get search statistics summary within a given date range.
        returning the sum of token counts.
        
        Args:
            start_date (datetime): The start of the date range.
            end_date (datetime): The end of the date range.

        Returns:
            Dict[str, int]: A dictionary containing the sum of token counts:
                            - total_prompt_tokens
                            - total_candidates_tokens
                            - total_thoughts_tokens
                            - total_tokens
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:    
            end_date = datetime.now()

        self.logger.info(f"Fetching search stat summary from {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            stats = self.db.get_search_stats(start_date=start_date, end_date=end_date)
            self.logger.info(f"Retrieved {len(stats)} search stat entries for the period.")
            
            summary = {
                "total_prompt_tokens": sum(s.get('prompt_token_count', 0) for s in stats),
                "total_candidates_tokens": sum(s.get('candidates_token_count', 0) for s in stats),
                "total_thoughts_tokens": sum(s.get('thoughts_token_count', 0) for s in stats),
                "total_tokens": sum(s.get('total_token_count', 0) for s in stats)
            }
            return summary
        except Exception as e:
            self.logger.error(f"Error getting search stat summary: {e}", exc_info=True)
            return {}
    
    def get_watch_history_grouped(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Retrieves watch history within a given date range and groups it by user.
        If no dates are provided, retrieves all watch history.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                                  represents a user and their watch history.
                                  Example: [{'user': 'user1', 'history': [...]}, ...]
        """
        if start_date and end_date:
            self.logger.info(f"Fetching and grouping watch history by user from {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}.")
        elif start_date:
            self.logger.info(f"Fetching and grouping watch history by user from {start_date.strftime('%Y-%m-%d %H:%M:%S')}.")
        elif end_date:
            self.logger.info(f"Fetching and grouping watch history by user up to {end_date.strftime('%Y-%m-%d %H:%M:%S')}.")
        else:
            self.logger.info("Fetching and grouping all watch history by user.")
        try:
            all_watch_history = self.db.get_watch_history(limit=None, start_date=start_date, end_date=end_date)
            
            user_history_map: Dict[str, List[Dict[str, Any]]] = {}
            for entry in all_watch_history:
                user = entry.get('watched_by')
                if user:
                    if user not in user_history_map:
                        user_history_map[user] = []
                    user_history_map[user].append(entry)
            
            return [{'user': user, 'history': history_items} for user, history_items in user_history_map.items()]
        except Exception as e:
            self.logger.error(f"Error getting grouped watch history: {e}", exc_info=True)
            return []

    def get_media_by_field(self, col_name: str) -> List[Any]:
        """
        Get unique values from a specific column in the media table.

        Args:
            col_name (str): The name of the column to query for unique values.

        Returns:
            List[Any]: A list of unique, potentially split, values from the specified column.
        """
        self.logger.info(f"Retrieving unique media values for column: {col_name}")
        try:
            return self.db.get_unique_media_values_by_field(field_name=col_name)
        except Exception as e:
            self.logger.error(f"Error in AiArr getting unique media values for column '{col_name}': {e}", exc_info=True)
            return []

    def trigger_scheduled_job(self, job_id: str) -> Dict[str, Any]:
        """
        Manually triggers a specific scheduled job to run immediately.

        Args:
            job_id (str): The ID of the job to trigger.

        Returns:
            Dict[str, Any]: A dictionary with "success" (bool) and "message" (str).
        """
        self.logger.info(f"Attempting to trigger scheduled job: {job_id}")
        job_exists = self.scheduler.get_job(job_id) is not None # self.scheduler is AiArrScheduler
        if not job_exists:
            self.logger.warning(f"Job '{job_id}' not found for triggering.")
            return {"success": False, "message": f"Job '{job_id}' not found."}

        if self.scheduler.trigger_job_now(job_id):
            return {"success": True, "message": f"Job '{job_id}' has been triggered to run now."}
        else:
            # trigger_job_now in AiArrScheduler already logs specific errors
            return {"success": False, "message": f"Failed to trigger job '{job_id}'. Check server logs for details."}
