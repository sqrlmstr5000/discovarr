import logging
from typing import Optional, Dict, List, Any, Union

from .settings import SettingsService
from providers.gemini import GeminiProvider
from providers.ollama import OllamaProvider

class LLMService:
    """
    Service to manage interactions with various LLM providers.
    """

    def __init__(self,
                 logger: logging.Logger,
                 settings_service: SettingsService,
                 enabled_llm_provider_names: List[str],
                 gemini_provider: Optional[GeminiProvider] = None,
                 ollama_provider: Optional[OllamaProvider] = None):
        self.logger = logger
        self.settings = settings_service
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
