import logging
from typing import Optional, Dict, List, Any, Union
from jinja2 import Template

from .settings import SettingsService
from providers.gemini import GeminiProvider
from providers.ollama import OllamaProvider
from .database import Database # Import Database for type hinting

class LLMService:
    """
    Service to manage interactions with various LLM providers.
    """

    def __init__(self,
                 logger: logging.Logger,
                 settings_service: SettingsService,
                 db_service: Database, # Add db_service parameter
                 enabled_llm_provider_names: List[str],
                 gemini_provider: Optional[GeminiProvider] = None,
                 ollama_provider: Optional[OllamaProvider] = None):
        self.logger = logger
        self.settings = settings_service
        self.db = db_service # Store the database service instance
        self.enabled_llm_provider_names = enabled_llm_provider_names
        self.gemini_provider = gemini_provider
        self.ollama_provider = ollama_provider


        if not self.enabled_llm_provider_names:
            self.logger.info("No LLM providers are enabled in the configuration.")
        else:
            self.logger.info(f"Enabled LLM providers: {self.enabled_llm_provider_names}")

    async def generate_suggestions(self, prompt: str, system_prompt: Optional[str], **kwargs) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generates media suggestions using the first available and configured LLM provider.
        """
        if not self.enabled_llm_provider_names:
            self.logger.warning("No LLM provider is enabled or configured to generate suggestions.")
            return {'success': False, 'message': "No LLM provider is enabled or configured.", 'status_code': 503}

        for provider_name in self.enabled_llm_provider_names:
            self.logger.debug(f"Attempting to use LLM provider: {provider_name}")
            if provider_name == GeminiProvider.PROVIDER_NAME and self.gemini_provider:
                gemini_model = self.settings.get("gemini", "model")
                gemini_temp = self.settings.get("gemini", "temperature")
                gemini_tb = self.settings.get("gemini", "thinking_budget")
                if not gemini_model:
                    self.logger.error("Gemini is enabled, but its model is not configured. Trying next provider.")
                    continue
                self.logger.info(f"Using Gemini provider (Model: {gemini_model}) for suggestions.")
                return await self.gemini_provider.get_similar_media(
                    prompt=prompt,
                    model=gemini_model,
                    system_prompt=system_prompt,
                    temperature=gemini_temp,
                    thinking_budget=gemini_tb,
                    **kwargs
                )
            elif provider_name == OllamaProvider.PROVIDER_NAME and self.ollama_provider:
                ollama_model = self.settings.get("ollama", "model")
                ollama_temp = self.settings.get("ollama", "temperature")
                if not ollama_model:
                    self.logger.error("Ollama is enabled, but its model is not configured. Trying next provider.")
                    continue
                self.logger.info(f"Using Ollama provider (Model: {ollama_model}) for suggestions.")
                return await self.ollama_provider.get_similar_media(
                    prompt=prompt,
                    model=ollama_model,
                    system_prompt=system_prompt,
                    temperature=ollama_temp,
                    **kwargs
                )
        
        self.logger.error("All enabled LLM providers are misconfigured (e.g., missing model name). Cannot generate suggestions.")
        return {'success': False, 'message': "Enabled LLM providers are misconfigured.", 'status_code': 500}

    async def generate_content(self,
                               prompt_data: Any,
                               response_format_details: Optional[Any] = None,
                               system_prompt: Optional[str] = None,
                               **kwargs: Any) -> Dict[str, Any]:
        """
        Generates content using the first available and configured LLM provider's
        low-level _generate_content method.

        Args:
            prompt_data (Any): The primary prompt data, type depends on the provider
                               (e.g., string for Gemini, list of messages for Ollama).
            response_format_details (Optional[Any]): Provider-specific details for response formatting.
            system_prompt (Optional[str]): System instructions for the LLM.
            **kwargs: Additional provider-specific parameters (e.g., thinking_budget).

        Returns:
            Dict[str, Any]: A dictionary containing 'success' (bool), 'content' (Any),
                            'token_counts' (Optional[Dict]), and 'message' (Optional[str]).
        """
        if not self.enabled_llm_provider_names:
            self.logger.warning("No LLM provider is enabled or configured to generate content.")
            return {'success': False, 'content': None, 'token_counts': None, 'message': "No LLM provider is enabled or configured."}

        for provider_name in self.enabled_llm_provider_names:
            self.logger.debug(f"Attempting to use LLM provider for generic content generation: {provider_name}")
            if provider_name == GeminiProvider.PROVIDER_NAME and self.gemini_provider:
                gemini_model = self.settings.get("gemini", "model")
                gemini_temp = self.settings.get("gemini", "temperature")
                gemini_tb = self.settings.get("gemini", "thinking_budget") # This could also come from kwargs
                if not gemini_model:
                    self.logger.error("Gemini is enabled, but its model is not configured. Trying next provider.")
                    continue
                self.logger.info(f"Using Gemini provider (Model: {gemini_model}) for generic content generation.")
                return await self.gemini_provider._generate_content(model=gemini_model, prompt_data=prompt_data, system_prompt=system_prompt, temperature=gemini_temp, response_format_details=response_format_details, thinking_budget=kwargs.get('thinking_budget', gemini_tb), **kwargs)
            elif provider_name == OllamaProvider.PROVIDER_NAME and self.ollama_provider:
                ollama_model = self.settings.get("ollama", "model")
                ollama_temp = self.settings.get("ollama", "temperature")
                if not ollama_model:
                    self.logger.error("Ollama is enabled, but its model is not configured. Trying next provider.")
                    continue
                self.logger.info(f"Using Ollama provider (Model: {ollama_model}) for generic content generation.")
                # Note: For Ollama, system_prompt is typically part of prompt_data (list of messages)
                return await self.ollama_provider._generate_content(model=ollama_model, prompt_data=prompt_data, system_prompt=system_prompt, temperature=ollama_temp, response_format_details=response_format_details, **kwargs)
        
        self.logger.error("All enabled LLM providers are misconfigured (e.g., missing model name). Cannot generate content.")
        return {'success': False, 'content': None, 'token_counts': None, 'message': "Enabled LLM providers are misconfigured."}

    def get_prompt(self, limit: int, media_name: Optional[str] = None, template_string: Optional[str] = None) -> str:
        """
        Renders a prompt string using Jinja2 templating.

        Args:
            limit (int): The limit to be used in the template.
            media_name (str): The media name to be used in the template.
            template_string (str): The Jinja2 template string.

        Returns:
            str: The rendered prompt string.
        """
        try:
            self.logger.debug(f"Prompt limit: {limit}")
            self.logger.debug(f"Prompt media_name: {media_name}")
            self.logger.debug(f"Prompt template_string: {template_string}")
            # Get current movies and series from jellyfin to exclude from suggestions
            all_media_for_exclusion = []
            if self.jellyfin_enabled and self.jellyfin_enable_media:
                self.logger.debug("Jellyfin media enabled, fetching for exclusion list.")
                jellyfin_media = self.jellyfin.get_all_items_filtered(attribute_filter="Name")
                if jellyfin_media: all_media_for_exclusion.extend(jellyfin_media)
            if self.plex_enabled and self.plex_enable_media: # Add Plex media if Plex is configured and media enabled
                self.logger.debug("Plex media enabled, fetching for exclusion list.")
                plex_media = self.plex.get_all_items_filtered(attribute_filter="name") # ItemsFiltered uses 'name'
                if plex_media: all_media_for_exclusion.extend(plex_media)
                
            # Trakt media exclusion is not typically done this way, so self.trakt_enable_media is not used here.
            # TODO: Add support for listing out entire Trakt collection. Does that even make sense in this context?

            self.logger.debug(f"{len(all_media_for_exclusion)} titles found")
            # Get ignored suggestions to exclude as well
            all_ignored = self.db.get_ignored_media_titles()
            self.logger.debug(f"{len(all_ignored)} titles to ignore")
            # Combine lists and convert to a comma-separated string
            all_ignored_str = ",".join(all_ignored + all_media_for_exclusion)
            self.logger.info("Finding similar media for: %s", media_name)
            self.logger.info("Exclude: %s", all_ignored_str)

            # Template variables
            favorites_str = ""
            all_favorites = []
            watch_history_str = ""
            all_watch_history = []

            # Fetch Jellyfin
            if self.jellyfin_enabled and self.jellyfin_enable_media: # Favorites are a type of "media" list
                self.logger.debug("Jellyfin media enabled, fetching favorites.")
                jellyfin_default_user_setting = self.settings.get("jellyfin", "default_user")
                self.logger.debug(f"Jellyfin default_user setting for favorites: {jellyfin_default_user_setting}")
                if jellyfin_default_user_setting:
                    user = self.jellyfin.get_user_by_name(username=jellyfin_default_user_setting)
                    if user:
                        # Get favorites
                        self.logger.debug(f"Fetching Jellyfin favorites for specific user: {user.name}")
                        user_favorites_items = self.jellyfin.get_favorites(user_id=user.id) 
                        if user_favorites_items:
                            user_favorites_names = [fav.name for fav in user_favorites_items if fav.name]
                            all_favorites.extend(user_favorites_names)
                            self.logger.debug(f"Jellyfin User {user.name} favorites: {user_favorites_names}")
                    else:
                        self.logger.warning(f"Jellyfin default user '{jellyfin_default_user_setting}' not found")
                else: 
                    self.logger.debug("Fetching Jellyfin favorites for all users.")
                    all_jellyfin_users = self.jellyfin.get_users()
                    if all_jellyfin_users:
                        for user_in_loop in all_jellyfin_users:
                            user_favorites_items = self.jellyfin.get_favorites(user_id=user_in_loop.id) 
                            if user_favorites_items:
                                user_favorites_names = [fav.name for fav in user_favorites_items if fav.name]
                                self.logger.debug(f"Jellyfin User {user_in_loop.name} favorites: {user_favorites_names}")
                                all_favorites.extend(user_favorites_names)

            # Fetch Plex
            if self.plex_enabled and self.plex_enable_media: # Favorites are a type of "media" list
                self.logger.debug("Plex media enabled, fetching favorites.")
                plex_default_user_setting = self.settings.get("plex", "default_user")
                self.logger.debug(f"Plex default_user setting for favorites: {plex_default_user_setting}")
                plex_user_context_id_for_api = None

                if plex_default_user_setting:
                    plex_user_obj = self.plex.get_user_by_name(plex_default_user_setting)
                    if plex_user_obj:
                        self.logger.debug(f"Fetching Plex favorites for specific user: {plex_user_obj.name}")
                        plex_user_context_id_for_api = plex_user_obj.id
                        plex_user_context_name_for_log = plex_user_obj.name
                        plex_favs_items = self.plex.get_favorites(user_id=plex_user_context_id_for_api) 
                        if plex_favs_items:
                            plex_favs_names = [fav.name for fav in plex_favs_items if fav.name]
                            all_favorites.extend(plex_favs_names)
                            self.logger.debug(f"Plex User context '{plex_user_context_name_for_log}' favorites (names): {plex_favs_names}")
                        else:
                            self.logger.warning(f"Plex default user '{plex_default_user_setting}' not found")
                else: 
                    self.logger.debug("No default Plex user specified. Fetching favorites for all Plex users.")
                    all_plex_users = self.plex.get_users()
                    if all_plex_users:
                        for plex_user_in_loop in all_plex_users:
                            user_favorites_items = self.plex.get_favorites(user_id=plex_user_in_loop.id)
                            if user_favorites_items:
                                user_favorites_names = [fav.name for fav in user_favorites_items if fav.name]
                                self.logger.debug(f"Plex User {plex_user_in_loop.name} favorites: {user_favorites_names}")
                                all_favorites.extend(user_favorites_names)

            self.logger.debug(f"All favorites count: {len(all_favorites)}")
            if len(all_favorites) > 0:
                favorites_str = ",".join(all_favorites)
                self.logger.info(f"Favorite Media: {favorites_str}")

            # Get watch history from DB. The DB is populated by sync_watch_history,
            # which respects the enable_history flags of providers.
            # So, if a provider's history is disabled, it won't be in the DB to begin with.
            # No direct check of enable_history is needed here for fetching from DB.
            self.logger.debug(f"Fetching watch history from database for prompt...")
            db_watch_history = self.db.get_watch_history(limit=None) # Get all watch history from DB
            if db_watch_history:
                watch_history_names = [o["title"] for o in db_watch_history if o["title"]]
                # Deduplicate and sort for consistency in the prompt
                unique_watch_history_names = sorted(list(set(watch_history_names)))
                all_watch_history.extend(unique_watch_history_names)

            self.logger.debug(f"Total unique watch history titles for prompt: {len(all_watch_history)}")
            if all_watch_history:
                watch_history_str = ",".join(all_watch_history)
                self.logger.info(f"Watch History: {watch_history_str}")

            if not template_string:
                template_string = self.default_prompt

            template = Template(template_string)
            rendered_prompt = template.render(
                limit=limit, media_name=media_name, media_exclude=all_ignored_str, all_media=all_ignored_str, favorites=favorites_str, watch_history=watch_history_str
            )
            return rendered_prompt
        except Exception as e:
            self.logger.error(f"Error rendering Jinja2 template: {e}", exc_info=True)
            # Depending on desired behavior, you might return an empty string or raise the exception
            return f"Error rendering prompt: {e}"

    def get_research_prompt(self, media_name: Optional[str] = None, template_string: Optional[str] = None) -> str:
        """
        Renders a prompt string using Jinja2 templating.

        Args:
            media_name (str): The media name to be used in the template.
            template_string (str): The Jinja2 template string.

        Returns:
            str: The rendered prompt string.
        """
        try:
            self.logger.debug(f"Prompt media_name: {media_name}")
            self.logger.debug(f"Prompt template_string: {template_string}")
            
            if not template_string:
                template_string = self.default_prompt

            template = Template(template_string)
            rendered_prompt = template.render(
                media_name=media_name,
            )
            return rendered_prompt
        except Exception as e:
            self.logger.error(f"Error rendering Jinja2 template: {e}", exc_info=True)
            # Depending on desired behavior, you might return an empty string or raise the exception
            return f"Error rendering prompt: {e}"

    async def get_available_models(self) -> Dict[str, Optional[List[str]]]:
        """
        Retrieves available models from all enabled LLM providers.
        """
        all_models: Dict[str, Optional[List[str]]] = {}

        if GeminiProvider.PROVIDER_NAME in self.enabled_llm_provider_names and self.gemini_provider:
            self.logger.info(f"Fetching models for {GeminiProvider.PROVIDER_NAME}")
            all_models[GeminiProvider.PROVIDER_NAME] = await self.gemini_provider.get_models()
        
        if OllamaProvider.PROVIDER_NAME in self.enabled_llm_provider_names and self.ollama_provider:
            self.logger.info(f"Fetching models for {OllamaProvider.PROVIDER_NAME}")
            all_models[OllamaProvider.PROVIDER_NAME] = await self.ollama_provider.get_models()

        if not all_models:
            self.logger.warning("No LLM providers enabled or failed to fetch models from any enabled provider.")
        
        return all_models
