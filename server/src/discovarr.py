import requests
import json
import logging
import sys
import os
import traceback 
from datetime import datetime, timedelta
from urllib.parse import urljoin
from typing import Optional, Dict, List, Any, Union
import asyncio 
import aiohttp # For async HTTP requests in the caching task
from peewee import fn
from services.models import ItemsFiltered, LibraryUser, Media # Import Media model
from services.radarr import Radarr # Keep Radarr import
from services.sonarr import Sonarr
from services.tmdb import TMDB
from services.database import Database
from services.scheduler import DiscovarrScheduler
from services.settings import SettingsService
from services.response import APIResponse
from services.image_cache import ImageCacheService 
from services.llm import LLMService # Import the new LLMService
from services.research import ResearchService # Import ResearchService
from providers.jellyfin import JellyfinProvider
from providers.plex import PlexProvider
from providers.ollama import OllamaProvider # Changed from Ollama
from providers.gemini import GeminiProvider # Keep GeminiProvider import
from providers.trakt import TraktProvider # Import TraktProvider

class Discovarr:
    """
    A class to interact with media servers and LLM APIs for media requests and management.
    """

    def __init__(self, db_path: Optional[str] = "/config/discovarr.db"):
        """
        Initializes the Discovarr class and sets up logging and API configurations.

        Args:
            db_path (Optional[str]): Path to the SQLite database file. Defaults to /config/discovarr.db.
        """
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Discovarr class...")

        now = datetime.now()
        local_tz = now.astimezone().tzinfo
        self.logger.info(f"Current system time: {now.strftime('%Y-%m-%d %H:%M:%S')} Timezone: {local_tz}")

        # Pass self (Discovarr instance) to SettingsService for callback
        self.settings = SettingsService(discovarr_app=self)

        # Initialize attributes to None or default before first load
        # This helps with type hinting and ensures attributes exist
        self.recent_limit = None
        self.suggestion_limit = None
        self.request_only = None
        self.default_prompt = None
        self.jellyfin_enabled = None 
        self.jellyfin_enable_media = None
        self.jellyfin_enable_history = None
        self.jellyfin_url = None
        self.plex_url = None 
        self.plex_enabled = None 
        self.plex_enable_media = None
        self.plex_enable_history = None
        self.plex_api_key = None 
        self.jellyfin_api_key = None
        self.radarr_api_key = None
        self.radarr_default_quality_profile_id = None
        self.radarr_root_dir_path = None
        self.sonarr_url = None
        self.sonarr_api_key = None
        self.sonarr_default_quality_profile_id = None
        self.sonarr_root_dir_path = None
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
        self.trakt_enabled = None
        self.trakt_enable_media = None # Trakt doesn't really have "media" in the same sense for exclusion, but history is key.
        self.trakt_enable_history = None
        self.trakt_client_id = None
        self.trakt_client_secret = None
        self.trakt_redirect_uri = None
        # self.trakt_access_token = None # Access token might be managed via OAuth flow
        self.auto_media_save = None
        self.system_prompt = None 

        self.enabled_providers: Dict[str, List[str]] = {
            "library": [],
            "llm": [],
            "request": []
        }
        self.plex = None # Initialize Plex service instance
        self.jellyfin = None
        self.radarr = None
        self.sonarr = None
        self.gemini = None
        self.ollama = None
        self.trakt = None # Initialize Trakt service instance
        self.llm_service = None # Initialize LLMService instance
        self.tmdb = None
        self.research_service = None # Initialize ResearchService instance

        self.db_path = db_path
        self.image_cache = ImageCacheService() # Initialize ImageCacheService
        # Load backup setting first as it's needed for Database initialization
        # Initialize Database with the backup setting
        self.db = Database(self.db_path)
        
        # Now that the database is initialized by self.db,
        # we can initialize the settings in the database.
        self.settings._initialize_settings()
        # Load the rest of the configuration and (re)initialize other services
        try:
            self.reload_configuration()
        except ValueError as e:
            self.logger.critical(f"Fatal configuration error during startup: {e}. Exiting.")
            sys.exit(1)

        # Initialize scheduler (depends on a fully configured Discovarr instance)
        self.scheduler = DiscovarrScheduler(db=self.db, discovarr_instance=self)
        self.logger.info("Scheduler initialized")
    def reload_configuration(self) -> None:
        """Loads/reloads configuration from settings and (re)initializes services."""
        self.logger.info("Loading/Reloading Discovarr configuration...")

        # Load configuration values from SettingsService_
        self.recent_limit = self.settings.get("app", "recent_limit")
        self.suggestion_limit = self.settings.get("app", "suggestion_limit")
        self.request_only = self.settings.get("app", "request_only")
        self.default_prompt = self.settings.get("app", "default_prompt")
        self.auto_media_save = self.settings.get("app", "auto_media_save")
        self.plex_enabled = self.settings.get("plex", "enabled") # Load Plex enabled status
        self.plex_enable_media = self.settings.get("plex", "enable_media")
        self.plex_enable_history = self.settings.get("plex", "enable_history")
        self.plex_url = self.settings.get("plex", "url") # Load Plex settings
        self.plex_api_key = self.settings.get("plex", "api_key") # Load Plex settings
        self.jellyfin_enabled = self.settings.get("jellyfin", "enabled") # Load Jellyfin enabled status
        self.jellyfin_enable_media = self.settings.get("jellyfin", "enable_media")
        self.jellyfin_enable_history = self.settings.get("jellyfin", "enable_history")
        self.jellyfin_url = self.settings.get("jellyfin", "url")
        self.jellyfin_api_key = self.settings.get("jellyfin", "api_key")
        self.radarr_url = self.settings.get("radarr", "url")
        self.radarr_api_key = self.settings.get("radarr", "api_key")
        self.radarr_default_quality_profile_id = self.settings.get("radarr", "default_quality_profile_id")
        self.radarr_root_dir_path = self.settings.get("radarr", "root_dir_path")
        self.sonarr_url = self.settings.get("sonarr", "url")
        self.sonarr_api_key = self.settings.get("sonarr", "api_key")
        self.sonarr_default_quality_profile_id = self.settings.get("sonarr", "default_quality_profile_id")
        self.sonarr_root_dir_path = self.settings.get("sonarr", "root_dir_path")
        self.gemini_enabled = self.settings.get("gemini", "enabled") 
        self.gemini_api_key = self.settings.get("gemini", "api_key")
        self.gemini_model = self.settings.get("gemini", "model")
        self.gemini_thinking_budget = self.settings.get("gemini", "thinking_budget")
        self.gemini_temperature = self.settings.get("gemini", "temperature")
        self.ollama_enabled = self.settings.get("ollama", "enabled")
        self.ollama_base_url = self.settings.get("ollama", "base_url")
        self.ollama_model = self.settings.get("ollama", "model")
        self.ollama_temperature = self.settings.get("ollama", "temperature")
        self.trakt_enabled = self.settings.get("trakt", "enabled")
        self.trakt_enable_media = self.settings.get("trakt", "enable_media") # Though less relevant for Trakt media exclusion
        self.trakt_enable_history = self.settings.get("trakt", "enable_history")
        self.trakt_client_id = self.settings.get("trakt", "client_id")
        self.trakt_client_secret = self.settings.get("trakt", "client_secret")
        self.trakt_redirect_uri = self.settings.get("trakt", "redirect_uri")
        self.tmdb_api_key = self.settings.get("tmdb", "api_key")
        self.system_prompt = self.settings.get("app", "system_prompt")
        
        # Reset and populate enabled_providers dictionary
        self.enabled_providers: Dict[str, List[str]] = {
            "library": [],
            "llm": [],
            "request": []
        }

        if self.jellyfin_enabled:
            self.enabled_providers["library"].append("jellyfin") # Use string literal
        if self.plex_enabled:
            self.enabled_providers["library"].append("plex")     # Use string literal
        if self.trakt_enabled:
            self.enabled_providers["library"].append("trakt")   # Use string literal
        
        if self.gemini_enabled:
            self.enabled_providers["llm"].append("gemini")   # Use string literal
        if self.ollama_enabled:
            self.enabled_providers["llm"].append("ollama")   # Use string literal

        # Radarr and Sonarr are "enabled" if their URL and API key are configured
        if self.radarr_url and self.radarr_api_key:
            self.enabled_providers["request"].append("radarr")
        if self.sonarr_url and self.sonarr_api_key:
            self.enabled_providers["request"].append("sonarr")
            
        # Log enabled providers for each category
        any_providers_enabled = False
        for category, providers_list in self.enabled_providers.items():
            if providers_list: # Only log if there are providers in the category
                self.logger.info(f"Enabled {category.capitalize()} Providers: {', '.join(providers_list)}")
                any_providers_enabled = True
        if not any_providers_enabled:
            self.logger.info("No providers are currently enabled.") 

        # Validate the loaded configuration
        try:
            self._validate_configuration()
        except ValueError as e:
            self.logger.error(f"Configuration validation error: {e}")
 
        # (Re)Initialize services with the new configuration
        self.plex = None # Reset before potential re-init
        self.jellyfin = None # Reset before potential re-init
        self.trakt = None # Reset before potential re-init

        if self.plex_enabled and self.plex_url and self.plex_api_key:
             self.plex = PlexProvider(
                plex_url=self.plex_url,
                plex_api_key=self.plex_api_key,
                limit=self.recent_limit # Use recent_limit for default Plex limit
            )
             self.logger.info("Plex service initialized.")
        elif self.plex_enabled:
            self.logger.warning("Plex is enabled but URL or token is missing. Plex service not initialized.")
        else:
            self.logger.info("Plex integration is disabled.")

        if self.jellyfin_enabled and self.jellyfin_url and self.jellyfin_api_key:
            self.jellyfin = JellyfinProvider(
                jellyfin_url=self.jellyfin_url,
                jellyfin_api_key=self.jellyfin_api_key,
            )
            self.logger.info("Jellyfin service initialized.")
        elif self.jellyfin_enabled:
            self.logger.warning("Jellyfin is enabled but URL or API key is missing. Jellyfin service not initialized.")
        else:
            self.logger.info("Jellyfin integration is disabled.")
        self.logger.debug(f"Inspecting 'Radarr' in reload_configuration: {Radarr}") # New debug
        self.radarr = Radarr(
            url=self.radarr_url,
            api_key=self.radarr_api_key,
        )
        self.sonarr = Sonarr(
            url=self.sonarr_url,
            api_key=self.sonarr_api_key,
        )
        if self.gemini_enabled and self.gemini_api_key:
            self.gemini = GeminiProvider(
                gemini_api_key=self.gemini_api_key
            )
        else:
            self.gemini = None
            self.logger.info("Gemini API key not configured. Gemini service disabled.")

        if self.ollama_enabled and self.ollama_base_url:
            self.ollama = OllamaProvider(
                ollama_base_url=self.ollama_base_url,
            )
            self.logger.info("Ollama service initialized.")
        elif self.ollama_enabled:
            self.logger.warning("Ollama is enabled but Base URL or Model is missing. Ollama service not initialized.")
        else:
            self.logger.info("Ollama integration is disabled.")

        if self.trakt_enabled and self.trakt_client_id and self.trakt_client_secret:
            self.trakt = TraktProvider(
                client_id=self.trakt_client_id,
                client_secret=self.trakt_client_secret,
                redirect_uri=self.trakt_redirect_uri,
                discovarr_app=self # Pass the Discovarr instance
            )
            self.logger.info("Trakt service initialized.")
            # If Trakt is initialized but not authenticated, _authenticate might be called
            # during TraktProvider's __init__.
            # If you want to explicitly trigger it later (e.g., via an endpoint),
            # you might adjust TraktProvider's __init__ to not auto-authenticate
            # or provide a method to check auth status.
        else:
            self.logger.info("Trakt integration is disabled or missing Client ID/Secret.")
        self.tmdb = TMDB(tmdb_api_key=self.tmdb_api_key)

        # Initialize LLMService with configured providers and settings
        self.llm_service = LLMService(
            logger=self.logger,
            settings_service=self.settings,
            db_service=self.db, # Pass the database instance
            enabled_providers=self.enabled_providers,
            gemini_provider=self.gemini,
            ollama_provider=self.ollama,
            jellyfin_provider=self.jellyfin,
            plex_provider=self.plex,
            trakt_provider=self.trakt
        )
        # Initialize ResearchService
        self.research_service = ResearchService(
            settings_service=self.settings,
            llm_service=self.llm_service,
            db_service=self.db
        )
        self.logger.info("Discovarr configuration processed and services (re)initialized.")

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
            if not self.plex_api_key:
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
        
        if self.trakt_enabled:
            if not self.trakt_client_id:
                raise ValueError("Trakt Client ID is required when Trakt integration is enabled.")
            if not self.trakt_client_secret:
                raise ValueError("Trakt Client Secret is required when Trakt integration is enabled.")
   
    def get_prompt(self, limit: int, media_name: Optional[str] = None, template_string: Optional[str] = None) -> str:
        """
        Renders a prompt string using the LLMService.
        This method acts as a pass-through to the LLMService's get_prompt method.

        Args:
            limit (int): The limit to be used in the template.
            media_name (Optional[str]): The media name to be used in the template.
            template_string (Optional[str]): The Jinja2 template string.
                                            If None, LLMService will use its default.

        Returns:
            str: The rendered prompt string, or an error message string if rendering fails.
        """
        if not self.llm_service:
            self.logger.error("LLMService is not initialized. Cannot render prompt.")
            return "Error: LLMService not available to render prompt."
        
        # The LLMService's get_prompt method now handles fetching media for exclusion,
        # favorites, and watch history internally.
        return self.llm_service.get_prompt(limit=limit, media_name=media_name, template_string=template_string)

    async def get_similar_media(self, media_name: Optional[str] = None, custom_prompt: Optional[str] = None, search_id: Optional[int] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Gets similar media suggestions from an LLM provider.

        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any]]: 
                A list of suggestion dictionaries on success, 
                or an error dictionary {'success': False, 'message': ..., 'status_code': ...} on failure.
        """
        template_string = self.default_prompt
        if custom_prompt:
            template_string = custom_prompt
        prompt = self.llm_service.get_prompt(limit=self.suggestion_limit, media_name=media_name, template_string=template_string)

        if not self.llm_service:
            self.logger.error("LLMService is not initialized.")
            return {'success': False, 'message': "LLMService not initialized.", 'status_code': 500}

        ref = None
        if search_id:
            ref = {
                "method": "search",
                "search_id": search_id
            }
        else:
            ref = {
                "method": "search",
                "media_name": media_name
            }
        provider_result = await self.llm_service.generate_suggestions(
            prompt=prompt,
            system_prompt=self.system_prompt,
            reference=json.dumps(ref)
            # kwargs for specific providers can be passed here if LLMService is adapted
            # For now, temperature and thinking_budget are handled within LLMService via settings
        )

        if not provider_result: # Should ideally not happen if providers return error dicts
            self.logger.error(f"LLM provider returned an unexpected None result.")
            return {'success': False, 'message': f"LLM provider returned None.", 'status_code': 500}

        # Check if the provider_result indicates an error
        if provider_result.get('success') is False:
            self.logger.error(f"Error from LLM Service: {provider_result.get('message')}")
            return provider_result # Propagate the error dictionary

        # If successful, provider_result contains 'response' and 'token_counts'
        llm_api_response_content = provider_result.get('response')

        if not llm_api_response_content or not isinstance(llm_api_response_content.get("suggestions"), list):
            self.logger.error(f"LLM provider response content is missing 'suggestions' list or is malformed.")
            self.logger.debug(f"LLM Response Content: {llm_api_response_content}")
            return {'success': False, 'message': "LLM response malformed or missing suggestions.", 'status_code': 500}

        self.logger.info(f"Similar Media: {json.dumps(llm_api_response_content, indent=2)}")
        
        suggestions_from_llm = llm_api_response_content.get("suggestions", [])
        processed_suggestions_for_client: List[Dict[str, Any]] = []

        for media in suggestions_from_llm:
            title = media.get("title")
            media_type = media.get("mediaType") # Assuming this matches your Suggestion model
            
            if not title or not media_type:
                self.logger.warning(f"Skipping suggestion due to missing title or mediaType: {media}")
                continue
            
            # Lookup TMDB ID
            tmdb_lookup = self.tmdb.lookup_media(title, media_type)
            if tmdb_lookup:
                tmdb_id = tmdb_lookup.get("id")
                # Get media details from TMDB
                tmdb_media_detail = self.tmdb.get_media_detail(tmdb_id=tmdb_id, media_type=media_type)

                # Get poster art from TMDB if tmdb_media_detail is not None
                poster_url = None
                poster_url_source =  f"https://image.tmdb.org/t/p/w500{tmdb_media_detail.get('poster_path')}" 
                # Ensure we have a URL and an ID for caching. Only save to cache if necessary.
                if poster_url_source and tmdb_id and (self.auto_media_save or search_id): 
                    poster_url = await self._cache_image_if_needed(poster_url_source, "media", tmdb_id)

                # Data validation
                rt_score = media.get("rt_score")
                if rt_score and isinstance(rt_score, str):
                    rt_score = int(rt_score.replace("%", ""))

                # Prepare network data
                network_names = []
                if media_type == "tv" and tmdb_media_detail and tmdb_media_detail.get("networks"):
                    network_names = [net.get("name") for net in tmdb_media_detail.get("networks", []) if net.get("name")]
                elif media_type == "movie":
                    network_names = None

                # Prepare genres data
                genre_names = []
                if tmdb_media_detail and tmdb_media_detail.get("genres"):
                    genre_names = [g.get("name") for g in tmdb_media_detail.get("genres", [])]

                release_date_val = tmdb_media_detail.get("release_date") if media_type == "movie" and tmdb_media_detail else (tmdb_media_detail.get("last_air_date") if tmdb_media_detail else None)

                # Search for existing media in database
                existing_media = self.db.search_media(title) # This returns a list
                if not existing_media:
                    # Create new media entry if it doesn't exist
                    media_data = {
                        "title": title,
                        "entity_type": "suggestion", 
                        "source_title": media_name,
                        "description": media.get("description"),
                        "similarity": media.get("similarity"),
                        "media_type": media_type,
                        "tmdb_id": tmdb_id,
                        "poster_url": poster_url,
                        "poster_url_source": poster_url_source,
                        "rt_url": media.get("rt_url"),
                        "rt_score": rt_score if isinstance(rt_score, int) else None,
                        "ignore": 0,  # Default to not ignored
                        "media_status": tmdb_media_detail.get("status") if tmdb_media_detail else None,
                        "release_date": release_date_val,
                        "networks": ", ".join(network_names) if network_names and isinstance(network_names, list) else None,
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
                        "poster_url": poster_url,
                        "poster_url_source": poster_url_source,
                        "rt_url": media.get("rt_url"),
                        "rt_score": rt_score if isinstance(rt_score, int) else None,
                        "media_status": tmdb_media_detail.get("status") if tmdb_media_detail else None,
                        "release_date": release_date_val,
                        "networks": ", ".join(network_names) if network_names and isinstance(network_names, list) else None,
                        "genres": ", ".join(genre_names) if genre_names else None,
                        "original_language": tmdb_media_detail.get("original_language"),
                    }
                    # Save results if running an ad-hoc search with the Auto Media Save option selected or when running a saved search.
                    if self.auto_media_save or search_id: 
                        update_success = self.db.update_media(existing_media_first.get("id"), media_data)
                        if update_success > 0: # Peewee update returns number of rows affected
                            self.logger.info(f"Updated media entry for {title}")
                        else:
                            self.logger.error(f"Failed to update media entry for {title}")

                self.logger.debug(f"Media: {media_data}")
                processed_suggestions_for_client.append(media_data)
        
        # This block should be outside the loop, after all suggestions are processed.
        if search_id:
            now = datetime.now()
            self.logger.debug(f"Updating Search ID: {search_id}, Last Run Date: {now}")
            self.db.update_search_run_date(search_id=search_id, last_run_date=now)

        return processed_suggestions_for_client
        # Error case is handled by returning the provider_result dictionary earlier

    def get_research_prompt(self, media_name: Optional[str] = None, template_string: Optional[str] = None) -> str:
        """
        Renders a prompt string using the LLMService.
        This method acts as a pass-through to the LLMService's get_prompt method.

        Args:
            media_name (Optional[str]): The media name to be used in the template.
            template_string (Optional[str]): The Jinja2 template string.
                                            If None, LLMService will use its default.

        Returns:
            str: The rendered prompt string, or an error message string if rendering fails.
        """
        if not self.llm_service:
            self.logger.error("LLMService is not initialized. Cannot render prompt.")
            return "Error: LLMService not available to render prompt."
        
        # The LLMService's get_prompt method now handles fetching media for exclusion,
        # favorites, and watch history internally.
        return self.llm_service.get_research_prompt(media_name=media_name, template_string=template_string)
    
    async def generate_research(self, media_name: str, media_id: Optional[int] = None, template_string: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates research content for a given media item using ResearchService.
        The ResearchService internally uses settings.app.default_research_prompt.

        Args:
            media_name (str): The name of the media to research.
            media_id (int): The ID of the Media record to associate with this research.

        Returns:
            Dict[str, Any]: A dictionary indicating success or failure,
                            and potentially the created research entry ID and text.
        """
        if not self.research_service:
            self.logger.error("ResearchService is not initialized. Cannot get research.")
            return {"success": False, "message": "ResearchService not available."}
        
        if media_name is None: # Basic validation
            self.logger.error("Media name is required for research.")
            return {"success": False, "message": "Media name is required."}

        return await self.research_service.generate_research(media_name=media_name, media_id=media_id, template_string=template_string)

    def get_all_research(self) -> List[Dict[str, Any]]:
        """
        Retrieves all research data entries from the database.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the MediaResearch entries,
                                  including associated media title. Returns an empty list on error.
        """
        self.logger.info("Retrieving all research entries.")
        try:
            return self.db.get_all_research()
        except Exception as e:
            self.logger.error(f"Error retrieving all research entries: {e}", exc_info=True)
            return [] # Return empty list on error
        
    def get_research_by_media_id(self, media_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves research data for a specific media item by its Media ID from the database.

        Args:
            media_id (int): The ID of the Media record.

        Returns:
            Optional[Dict[str, Any]]: A dictionary representing the MediaResearch entry, or None if not found.
        """
        self.logger.info(f"Retrieving research for media ID: {media_id}")
        try:
            return self.db.get_research_by_media_id(media_id)
        except Exception as e:
            self.logger.error(f"Error retrieving research for media ID {media_id}: {e}", exc_info=True)
            return None

    def delete_media_research(self, research_id: int) -> Dict[str, Any]:
        """
        Deletes a specific MediaResearch entry.

        Args:
            research_id (int): The ID of the MediaResearch entry to delete.

        Returns:
            Dict[str, Any]: A dictionary indicating success or failure.
        """
        self.logger.info(f"Attempting to delete MediaResearch entry with ID: {research_id}")
        if self.db.delete_media_research(research_id):
            self.logger.info(f"Successfully deleted MediaResearch entry {research_id}.")
            return {"success": True, "message": f"MediaResearch entry {research_id} deleted successfully."}
        else:
            # This could mean the entry was not found or a DB error occurred.
            # The db method logs specifics.
            self.logger.warning(f"Failed to delete MediaResearch entry {research_id}. It might not exist or a database error occurred.")
            return {"success": False, "message": f"MediaResearch entry {research_id} not found or could not be deleted.", "status_code": 404}

    def search_media(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches for media in the database based on a query string.

        Args:
            query (str): The search term.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing
                                  'title', 'media_id' (tmdb_id), and 'media_type'.
        """
        self.logger.info(f"Searching media with query: '{query}'")
        db_results = self.db.search_media(query)
        
        formatted_results = []
        for item in db_results:
            formatted_results.append({
                "title": item.get("title"),
                "media_id": item.get("id"),      # This is the Media table Primary Key
                "tmdb_id": item.get("tmdb_id"),  # Explicitly include tmdb_id
                "media_type": item.get("media_type")
            })
        return formatted_results

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

    async def get_llm_models(self) -> Dict[str, Optional[List[str]]]:
        """
        Retrieves available models from all enabled LLM providers via LLMService.

        Returns:
            Dict[str, Optional[List[str]]]: A dictionary where keys are provider names
                                            and values are lists of model names, or None if error.
        """
        if not self.llm_service:
            self.logger.error("LLMService is not initialized. Cannot retrieve LLM models.")
            return None
        return await self.llm_service.get_available_models()

    async def _cache_image_if_needed(self, image_url: str, provider_name: str, item_id: Union[str, int]) -> Optional[str]:
        """
        Asynchronously caches an image if a valid external URL is provided.
        Returns the path to the cached image or the original URL if caching is skipped/failed.
        """
        original_url = image_url # Keep original URL as fallback
        if not image_url or not item_id:
            self.logger.debug(f"Skipping image cache for {provider_name} item {item_id}: Missing URL or item ID.")
            return original_url

        # Check if the URL looks like it's already a local cached path
        if image_url.startswith(f"/{self.image_cache.cache_base_dir.name}/"):
            self.logger.debug(f"Skipping image cache for {provider_name} item {item_id}: URL '{image_url}' appears to be already cached.")
            return

        try:
            # Create a new session for each task for simplicity in fire-and-forget.
            # For very high volume, a shared session might be considered.
            async with aiohttp.ClientSession() as session:
                cached_path = await self.image_cache.save_image_from_url(session, image_url, provider_name, str(item_id))
                return cached_path if cached_path else original_url
        except Exception as e:
            self.logger.error(f"Exception in image caching task for {provider_name} item {item_id} (URL: {image_url}): {e}", exc_info=True)
        return original_url # Fallback to original URL on error

    async def _sync_watch_history_to_db(self, user_name: str, user_id: str, recently_watched_items: Optional[List[ItemsFiltered]], source: str) -> Optional[List[ItemsFiltered]]:
        """
        Helper method to filter and add/update watch history items in the database.
        `recently_watched_items` is expected to be a list of ItemsFiltered.
        Returns the list of unique, filtered items (ItemsFiltered) that were processed.
        """
        if recently_watched_items is None or not recently_watched_items:
            self.logger.info(f"No new recently watched items for {user_name} from {source} or error fetching.")
            return [] # Return empty list for consistency

        # Items are already ItemsFiltered, so unique_items is recently_watched_items
        unique_items = recently_watched_items

        # Ensure unique_items is indeed a list of ItemsFiltered
        if not all(isinstance(item, ItemsFiltered) for item in unique_items):
            self.logger.error(f"Received items for {source} are not all ItemsFiltered. Aborting DB sync for this batch.")
            return []

        if unique_items: # unique_items is List[ItemsFiltered]
            for item in unique_items: # item is ItemsFiltered
                if not isinstance(item, ItemsFiltered): # Defensive check
                    self.logger.warning(f"Skipping item due to unexpected type in unique_items for {source}: {type(item)}")
                    continue
                if not item.id or not item.type or not item.name:
                    self.logger.warning(f"Skipping item from {source} due to missing id, type, or name: {item}")
                    continue
                
                # Find or create Media record
                media_instance = Media.get_or_none((fn.Lower(Media.title) == item.name.lower()) & (Media.media_type == item.type))
                newly_created_media = False

                if not media_instance:
                    self.logger.info(f"Media '{item.name}', type: ({item.type}) not found in DB. Creating new entry from {source} watch history.")
                    tmdb_details = self.tmdb.get_media_detail(tmdb_id=item.id, media_type=item.type) if self.tmdb else None
                    
                    poster_url_source_val = item.poster_url # Use poster from provider if available
                    cached_poster_path = None

                    if not poster_url_source_val and tmdb_details and tmdb_details.get("poster_path"):
                        poster_url_source_val = f"https://image.tmdb.org/t/p/w500{tmdb_details.get('poster_path')}"
                    
                    if poster_url_source_val:
                         cached_poster_path = await self._cache_image_if_needed(poster_url_source_val, source, item.id)
                    
                    network_names = []
                    genre_names = []
                    release_date_val = None
                    original_language_val = None
                    description_val = None
                    media_status_val = None

                    if tmdb_details:
                        description_val = tmdb_details.get("overview")
                        media_status_val = tmdb_details.get("status")
                        original_language_val = tmdb_details.get("original_language")
                        release_date_val = tmdb_details.get("release_date") if item.type == "movie" else tmdb_details.get("last_air_date")
                        if item.type == "tv" and tmdb_details.get("networks"):
                            network_names = [net.get("name") for net in tmdb_details.get("networks", []) if net.get("name")]
                        if tmdb_details.get("genres"):
                            genre_names = [g.get("name") for g in tmdb_details.get("genres", [])]

                    media_data_for_creation = {
                        "title": item.name,
                        "tmdb_id": item.id,
                        "media_type": item.type,
                        "entity_type": "library", 
                        "source_provider": source,
                        "source_title": None, 
                        "description": description_val,
                        "poster_url": cached_poster_path,
                        "poster_url_source": poster_url_source_val,
                        "release_date": release_date_val,
                        "networks": ", ".join(network_names) if network_names else None,
                        "genres": ", ".join(genre_names) if genre_names else None,
                        "original_language": original_language_val,
                        "media_status": media_status_val,
                        "watched": True,
                        "favorite": item.is_favorite,
                        "watch_count": 1,
                        "ignore": False 
                    }
                    media_pk = self.db.create_media(media_data_for_creation)
                    if media_pk:
                        media_instance = Media.get_by_id(media_pk)
                        newly_created_media = True
                    else:
                        self.logger.error(f"Failed to create Media entry for '{item.name}'. Skipping WatchHistory add.")
                        continue 
                
                if media_instance:
                    add_history_success = self.db.add_watch_history(
                        media_id=media_instance.id, 
                        watched_by=user_name, 
                        last_played_date_iso=item.last_played_date
                    )
                    if add_history_success:
                        self.logger.info(f"Successfully added/updated WatchHistory for '{media_instance.title}' by {user_name}.")
                        watch_count = (media_instance.watch_count or 0) + 1
                        self.logger.info(f"Updating media instance '{media_instance.title}' with watch count: {watch_count} and watched status (True).")
                        if not newly_created_media: 
                            media_instance.watch_count = watch_count
                            media_instance.watched = True
                            media_instance.updated_at = datetime.now()
                            media_instance.save()
                    else:
                        self.logger.error(f"Skipped add/update WatchHistory for '{media_instance.title}' by {user_name}.")
                
            self.logger.info(f"Synced and added/updated {len(unique_items)} unique recently watched title(s) for {user_name} from {source}.")
            return unique_items
        return []
    
    async def sync_watch_history(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves the list of available Gemini models.

        Returns:
            Optional[List[Dict[str, Any]]]: A list of model details or None if Gemini service is not available or an error occurs.
        """
        all_users_data: Dict[str, Dict[str, Any]] = {}

        # Sync Jellyfin history
        if self.jellyfin_enabled and self.jellyfin_enable_history:
            jellyfin_users = self.jellyfin.get_users()
            if not jellyfin_users:
                self.logger.warning("No Jellyfin users found to sync watch history.")
            else:
                self.logger.info(f"Starting Jellyfin watch history sync for {len(jellyfin_users)} user(s).")
                for user_data in jellyfin_users:
                    user_name = user_data.name # user_data is LibraryUser
                    user_id = user_data.id # Access .id
                    if not user_name or not user_id:
                        self.logger.warning(f"Skipping Jellyfin user with missing Name or Id: {user_data}")
                        continue # user_data is LibraryUser
                    self.logger.debug(f"Syncing watch history for Jellyfin user: {user_name} (ID: {user_id})")

                    # Ensure user is in the results dict, even if no items are found later
                    all_users_data.setdefault(user_name, {"id": user_id, "recent_titles": []})

                    # TODO: Fix to check media table instead
                    history_count = self.db.get_media_count_for_provider("jellyfin")
                    limit_for_provider = None 
                    if history_count == 0:
                        self.logger.debug(f"Jellfin watch history count={history_count}, syncing all history.")
                    else:
                        self.logger.debug(f"Jellyfin watch history count={history_count}, syncing last {self.recent_limit} items from watch history.")
                        limit_for_provider =self.recent_limit
                    recently_watched_items = self.jellyfin.get_recently_watched(
                        user_id=user_id, limit=limit_for_provider
                    )
                    if recently_watched_items: # recently_watched_items is now List[ItemsFiltered]
                        synced_items = await self._sync_watch_history_to_db(user_name=user_name, user_id=user_id, recently_watched_items=recently_watched_items, source="jellyfin")
                        filtered_item_names = [item.name for item in synced_items]
                        all_users_data[user_name]["recent_titles"].extend(filtered_item_names)
        else:
            self.logger.debug("Jellyfin service not configured or history sync disabled. Skipping Jellyfin watch history sync.")

        # Sync Plex history
        if self.plex_enabled and self.plex_enable_history:
            plex_users = self.plex.get_users() # These are managed accounts
            if not plex_users: # If no managed users, consider syncing for the main account if desired
                self.logger.warning("No managed Plex users found to sync watch history.")
                # Optionally, you could add logic here to sync for the main account if plex_users is empty
            else:
                self.logger.info(f"Starting Plex watch history sync for {len(plex_users)} managed user(s).")
                for user_data in plex_users: # user_data is a dict from Plex API
                    user_name = user_data.name # user_data is LibraryUser
                    user_id = user_data.id # Access .id
                    if not user_name or not user_id:
                        self.logger.warning(f"Skipping Plex user with missing name or id: {user_data}")
                        continue
                    self.logger.debug(f"Syncing watch history for Plex user: {user_name} (ID: {user_id})")

                    # Ensure user is in the results dict, even if no items are found later
                    all_users_data.setdefault(user_name, {"id": user_id, "recent_titles": []})

                    # TODO: Fix to check media table instead
                    history_count = self.db.get_media_count_for_provider("plex")
                    limit_for_provider = None 
                    if history_count == 0:
                        self.logger.debug(f"Plex watch history count={history_count}, syncing all history.")
                    else:
                        self.logger.debug(f"Plex watch history count={history_count}, syncing last {self.recent_limit} items from watch history.")
                        limit_for_provider =self.recent_limit
                    recently_watched_items = self.plex.get_recently_watched(user_id=user_id, limit=limit_for_provider)
                    if recently_watched_items: # recently_watched_items is now List[ItemsFiltered]
                        synced_items = await self._sync_watch_history_to_db(user_name=user_name, user_id=user_id, recently_watched_items=recently_watched_items, source="plex")
                        filtered_item_names = [item.name for item in synced_items]
                        all_users_data[user_name]["recent_titles"].extend(filtered_item_names)
        else:
            self.logger.debug("Plex service not configured or history sync disabled. Skipping Plex watch history sync.")

        # Sync Trakt history
        if self.trakt_enabled and self.trakt_enable_history:
            trakt_users = self.trakt.get_users() # Trakt usually returns one user
            if not trakt_users:
                self.logger.warning("No Trakt users found to sync watch history.")
            else:
                self.logger.info(f"Starting Trakt watch history sync for {len(trakt_users)} user(s).")
                for user_data in trakt_users: # user_data is LibraryUser
                    user_name = user_data.name
                    user_id = user_data.id # Trakt user slug can be used as ID
                    self.logger.debug(f"Syncing watch history for Trakt user: {user_name} (ID: {user_id})")

                    # Ensure user is in the results dict, even if no items are found later
                    all_users_data.setdefault(user_name, {"id": user_id, "recent_titles": []})

                    history_count = self.db.get_media_count_for_provider("trakt")
                    limit_for_provider = None 
                    if history_count == 0:
                        self.logger.debug(f"Trakt watch history count={history_count}, syncing all history.")
                    else:
                        self.logger.debug(f"Trakt watch history count={history_count}, syncing last {self.recent_limit} items from watch history.")
                        limit_for_provider =self.recent_limit
                    recently_watched_items = self.trakt.get_recently_watched(user_id=user_id, limit=limit_for_provider)
                    if recently_watched_items: # recently_watched_items is now List[ItemsFiltered]
                        synced_items = await self._sync_watch_history_to_db(user_name=user_name, user_id=user_id, recently_watched_items=recently_watched_items, source="trakt")
                        filtered_item_names = [item.name for item in synced_items]
                        all_users_data[user_name]["recent_titles"].extend(filtered_item_names)
        else:
            self.logger.debug("Trakt service not configured or history sync disabled. Skipping Trakt watch history sync.")

        # Ensure uniqueness in recent_titles if a user exists in both systems with the same name
        for user_name_key in all_users_data:
            all_users_data[user_name_key]["recent_titles"] = sorted(list(set(all_users_data[user_name_key]["recent_titles"])))

        #self.logger.debug(f"Sync Watch History Results: {json.dumps(all_users_data, indent=2)}")
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

            request = self.radarr.add_movie(tmdb_id=tmdb_id, quality_profile_id=actual_quality_profile_id_to_use, search_for_movie=not self.request_only, root_dir_path=self.radarr_root_dir_path)
            self.logger.debug(f"Radarr Add Movie Response: {json.dumps(request.data, indent=2)}")
        elif media_type == "tv":
            if not actual_quality_profile_id_to_use: # Handles None or 0
                actual_quality_profile_id_to_use = self.sonarr_default_quality_profile_id
            
            if save_default and quality_profile_id is not None: # Use the user-selected profile ID
                self.logger.info(f"Saving Sonarr default quality profile ID: {quality_profile_id}")
                self.settings.set("sonarr", "default_quality_profile_id", quality_profile_id)
                # self.sonarr_default_quality_profile_id will be updated on next reload_configuration by settings service

            request = self.sonarr.add_series(tmdb_id=tmdb_id, quality_profile_id=actual_quality_profile_id_to_use, search_for_missing=not self.request_only, root_dir_path=self.sonarr_root_dir_path)
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

    def get_users(self) -> Optional[List[LibraryUser]]:
        """
        Get all users from enabled library providers (Jellyfin, Plex, Trakt).
        Returns a combined List[LibraryUser].

        Returns:
            Optional[List[LibraryUser]]: A combined list of user objects from all enabled providers,
                                         or None if no providers are enabled or an error occurs.
        """
        self.logger.info("Retrieving all users from enabled library providers.")
        all_users: List[LibraryUser] = []
        providers_queried = False

        if self.jellyfin:
            providers_queried = True
            jellyfin_users = self.jellyfin.get_users()
            if jellyfin_users:
                all_users.extend(jellyfin_users)
                self.logger.info(f"Retrieved {len(jellyfin_users)} users from Jellyfin.")
        if self.plex:
            providers_queried = True
            plex_users = self.plex.get_users()
            if plex_users:
                all_users.extend(plex_users)
                self.logger.info(f"Retrieved {len(plex_users)} users from Plex.")
        if self.trakt:
            providers_queried = True
            trakt_users = self.trakt.get_users() # Trakt usually returns one user
            if trakt_users:
                all_users.extend(trakt_users)
                self.logger.info(f"Retrieved {len(trakt_users)} users from Trakt.")

        if not providers_queried:
            self.logger.warning("No library providers (Jellyfin, Plex, Trakt) are configured/enabled to retrieve users.")
            return None
        
        # Consider de-duplicating users if the same user (by name or another unique ID) could come from multiple sources.
        # For now, it returns a combined list.
        self.logger.info(f"Total users retrieved from all providers: {len(all_users)}")
        return all_users
    def get_active_media(self) -> List[Dict[str, Any]]:
        """
        Get all non-ignored media entries from the database.

        Returns:
            List[Dict[str, Any]]: List of active media entries
        """
        return self.db.get_non_ignored_suggestions()

    def get_ignored_suggestions(self) -> List[Dict[str, Any]]:
        """
        Get all ignored media entries from the database.

        Returns:
            List[Dict[str, Any]]: List of ignored media entries
        """
        return self.db.get_ignored_suggestions()

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

    def delete_watch_history_item(self, history_item_id: int) -> Dict[str, Any]:
        """
        Deletes a specific watch history item from the database.

        Args:
            history_item_id (int): The ID of the watch history item to delete.

        Returns:
            Dict[str, Any]: A dictionary indicating success or failure.
                            Example: {"success": True, "message": "Item deleted."}
                                     {"success": False, "message": "Item not found.", "status_code": 404}
        """
        self.logger.info(f"Attempting to delete watch history item with ID: {history_item_id}")
        
        # First, try to get the item to retrieve its poster_url for cache deletion
        history_item = self.db.get_watch_history_item_by_id(history_item_id)
        
        if not history_item:
            self.logger.warning(f"Watch history item {history_item_id} not found for deletion.")
            return {"success": False, "message": f"Watch history item {history_item_id} not found or could not be deleted.", "status_code": 404}

        poster_filename = history_item.get('poster_url')
        if poster_filename:
            self.logger.info(f"Attempting to delete cached image '{poster_filename}' for history item {history_item_id}.")
            if not self.image_cache.delete_cached_image(poster_filename):
                self.logger.warning(f"Could not delete cached image '{poster_filename}' for history item {history_item_id}. Proceeding with DB deletion.")
                # Optionally, you could make this a hard failure if image deletion is critical

        if self.db.delete_watch_history_item(history_item_id):
            self.logger.info(f"Successfully deleted watch history item {history_item_id} from database.")
            return {"success": True, "message": f"Watch history item {history_item_id} deleted successfully."}
        
        self.logger.error(f"Failed to delete watch history item {history_item_id} from database after attempting image cache cleanup.")
        return {"success": False, "message": f"Failed to delete watch history item {history_item_id} from database.", "status_code": 500}

    def delete_all_watch_history(self) -> Dict[str, Any]:
        """
        Deletes all watch history items from the database.

        Returns:
            Dict[str, Any]: A dictionary indicating success or failure.
                            Example: {"success": True, "message": "All items deleted."}
                                     {"success": False, "message": "Error message.", "status_code": 500}
        """
        self.logger.info("Attempting to delete all watch history items.")
        try:
            # Get all history items to iterate for their poster_urls
            all_history_items = self.db.get_watch_history(limit=None)
            if all_history_items:
                self.logger.info(f"Found {len(all_history_items)} watch history items to process for image cache deletion.")
                for item in all_history_items:
                    poster_filename = item.get('poster_url')
                    if poster_filename:
                        self.logger.debug(f"Attempting to delete cached image '{poster_filename}' for history item ID {item.get('id')}.")
                        if not self.image_cache.delete_cached_image(poster_filename):
                            self.logger.warning(f"Could not delete cached image '{poster_filename}' for history item ID {item.get('id')}. Proceeding.")
            else:
                self.logger.info("No watch history items found to delete images for.")

            # Proceed to delete all history items from the database
            deleted_count = self.db.delete_all_watch_history()
            self.logger.info(f"Successfully deleted {deleted_count} watch history item(s).")
            return {"success": True, "message": f"Deleted {deleted_count} watch history item(s)."}
        except Exception as e:
            self.logger.error(f"Error during the process of deleting all watch history items: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to delete all watch history items: {e}", "status_code": 500}


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
            self.logger.error(f"Error in Discovarr getting unique media values for column '{col_name}': {e}", exc_info=True)
            return []
        
    async def add_watch_history_item_manual(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manually adds or updates a watch history item.
        This method is intended to be called by an API endpoint.
        `data` is expected to be a dictionary matching WatchHistoryCreateRequest.
        """
        self.logger.info(f"Attempting to add/update watch history item manually: {data.get('title')}")
        try:
            # Get initial values from input data that might be updated
            title = data.get('title')
            media_type = data.get('media_type')
            last_played_date_str = data.get('last_played_date')

            # Validate last_played_date if provided
            if last_played_date_str:
                try:
                    # Attempt to parse to ensure it's a valid ISO 8601 string
                    datetime.fromisoformat(last_played_date_str.replace('Z', '+00:00'))
                except ValueError:
                    self.logger.error(f"Invalid last_played_date format: {last_played_date_str}. Must be ISO 8601.")
                    return {"success": False, "message": f"Invalid last_played_date format: '{last_played_date_str}'. Must be a valid ISO 8601 string (e.g., '2023-10-26T10:00:00Z' or '2023-10-26T10:00:00+00:00').", "status_code": 400}
            else: # If not provided, it will be defaulted to now() in db.add_watch_history
                self.logger.info(f"last_played_date not provided for '{title}', will default to current time upon DB insertion.")

            if media_type not in ['tv', 'movie']:
                self.logger.error(f"Invalid media_type '{media_type}' provided. Must be 'tv' or 'movie'.")
                return {"success": False, "message": f"Invalid media_type '{media_type}'. Must be 'tv' or 'movie'.", "status_code": 400}
            
            # These will be used for db.add_watch_history and might be updated by lookup
            current_media_id = data.get('media_id')
            current_poster_url_source = data.get('poster_url_source')

            # If media_id is not set, try to look it up using title and media_type
            if not current_media_id and title and media_type and self.tmdb:
                self.logger.info(f"Media ID not provided for '{title}'. Attempting TMDB lookup by title.")
                tmdb_lookup_result = self.tmdb.lookup_media(query=title, media_type=media_type)
                if tmdb_lookup_result and tmdb_lookup_result.get("id"):
                    current_media_id = str(tmdb_lookup_result.get("id")) # Ensure media_id is a string
                    self.logger.info(f"Found TMDB ID '{current_media_id}' for '{title}'.")
                    # If poster_url_source was also missing (or not provided initially), try to get it from this lookup
                    if not current_poster_url_source and tmdb_lookup_result.get("poster_path"):
                        poster_path = tmdb_lookup_result.get("poster_path")
                        current_poster_url_source = f"https://image.tmdb.org/t/p/w500{poster_path}"
                        self.logger.info(f"Found poster URL from TMDB for '{title}': {current_poster_url_source}")
                else:
                    self.logger.warning(f"TMDB lookup by title failed for '{title}' or no ID/poster found.")
            
            # Image Caching
            final_poster_url = None
            source_provider = data.get('source', 'manual') # Default source to 'manual' if not provided
            # Use the (potentially updated) current_media_id for caching. Fallback to title if current_media_id is still None.
            media_id_for_cache = current_media_id or title

            if current_poster_url_source and media_id_for_cache:
                final_poster_url = await self._cache_image_if_needed(current_poster_url_source, source_provider, media_id_for_cache)

            success = self.db.add_watch_history(
                title=data['title'],
                media_id=current_media_id, # Use potentially updated media_id
                media_type=data['media_type'],
                watched_by=data['watched_by'],
                last_played_date=last_played_date_str, # Pass the validated or None string
                source=source_provider,
                poster_url=final_poster_url,
                poster_url_source=current_poster_url_source # Use potentially updated poster_url_source
            )

            if success:
                return {"success": True, "message": "Watch history item added/updated successfully."}
            else:
                return {"success": False, "message": "Failed to add/update watch history item in database.", "status_code": 500}
        except Exception as e:
            self.logger.error(f"Error manually adding/updating watch history item: {e}", exc_info=True)
            return {"success": False, "message": str(e), "status_code": 500}

    def trigger_scheduled_job(self, job_id: str) -> Dict[str, Any]:
        """
        Manually triggers a specific scheduled job to run immediately.

        Args:
            job_id (str): The ID of the job to trigger.

        Returns:
            Dict[str, Any]: A dictionary with "success" (bool) and "message" (str).
        """
        self.logger.info(f"Attempting to trigger scheduled job: {job_id}")
        job_exists = self.scheduler.get_job(job_id) is not None
        if not job_exists:
            self.logger.warning(f"Job '{job_id}' not found for triggering.")
            return {"success": False, "message": f"Job '{job_id}' not found."}

        if self.scheduler.trigger_job_now(job_id):
            return {"success": True, "message": f"Job '{job_id}' has been triggered to run now."}
        else:
            # trigger_job_now in DiscovarrScheduler already logs specific errors
            return {"success": False, "message": f"Failed to trigger job '{job_id}'. Check server logs for details."}
        
    # --- Trakt Methods ---
    def trakt_authenticate(self) -> Dict[str, Any]:
        """
        Initiates the Trakt authentication process.
        Returns a dictionary with success status, user_code, verification_url, and a message.
        """
        if not self.trakt:
            self.logger.warning("Trakt service not available or not enabled. Cannot authenticate.")
            return {"success": False, "message": "Trakt service not available or not enabled."}
        
        self.logger.info("Attempting to authenticate with Trakt...")
        # _authenticate in TraktProvider is blocking and handles the flow.
        # It now returns a dictionary.
        return self.trakt._authenticate()
