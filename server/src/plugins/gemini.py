import json
import logging
import sys  
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import asyncio # For running sync code in async
from google import genai
from google.genai import types
from services.models import Suggestion, SuggestionList
from services.llm_provider_base import LLMProviderBase
from services.models import SettingType # Import SettingType from models

class Gemini(LLMProviderBase):
    """
    A class to interact with the Gemini API for finding similar media.
    """
    PROVIDER_NAME = "gemini"
    def __init__(self, gemini_api_key: str):
        """
        Initializes the Gemini class with API configurations.

        Args:
            gemini_model (str): The Gemini model to use for generating content.
            client (Any): The Gemini API client instance.
        """
        # Setup Logging
        self.logger = logging.getLogger(__name__)

        self.gemini_api_key = gemini_api_key
        self.logger.info("Initializing Gemini class...")

        self.client = genai.Client(api_key=self.gemini_api_key)

    @property
    def name(self) -> str:
        """Returns the name of the LLM provider."""
        return self.PROVIDER_NAME

    async def get_similar_media(self, model: str, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = 0.7, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Uses the Gemini API to find media similar to the given media name.

        Rate limits for the Gemini API can be found here:
        https://ai.google.dev/gemini-api/docs/rate-limits#current-rate-limits

        Args:
            model (str): The Gemini model to use.
            prompt (str): The user's prompt for suggestions.
            system_prompt (Optional[str]): System instructions for the LLM.
            temperature (Optional[float]): Controls randomness.
            **kwargs: Additional provider-specific parameters.
                      Expected: 'thinking_budget' (Optional[float]).

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing:
                - 'response': The Gemini API response
                - 'token_counts': Dictionary with token usage statistics
                Or None on error
        """
        if not self.gemini_api_key:
            self.logger.error("Gemini API Key is not configured.")
            return None
        
        thinking_budget = kwargs.get('thinking_budget', 0.0)

        try:
            self.logger.debug(f"Using prompt: {prompt}")

            response = await self.client.aio.models.generate_content(model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=SuggestionList
                ))
            
            gemini_response = json.loads(response.text)
            
            # Extract token counts from usage metadata
            usage_meta = response.usage_metadata
            self.logger.debug(f"Gemini Usage Metadata: {usage_meta}")
            token_counts = {
                'prompt_token_count': usage_meta.prompt_token_count,
                'candidates_token_count': usage_meta.candidates_token_count,
                'thoughts_token_count': usage_meta.thoughts_token_count,
                'total_token_count': usage_meta.total_token_count,
            }
            
            self.logger.debug(f"Token usage stats: {token_counts}")
            
            return {
                'response': gemini_response,
                'token_counts': token_counts
            }
        except json.JSONDecodeError:
            error_message = "Gemini API returned non-JSON response."
            self.logger.error(error_message)
            self.logger.debug(response.text)
            return None
        except Exception as e:
            error_message = f"Gemini API error: {e}"
            self.logger.exception(error_message)  # Log the exception
            return None

    async def get_models(self) -> Optional[List[str]]:
        """
        Lists available Gemini and Gemma model names, with "models/" prefix removed.

        Returns:
            Optional[List[str]]: A list of approved model names (e.g., "gemini-pro", "gemma-7b"),
                                 or None on error.
        """
        if not self.client:
            self.logger.error("Gemini client is not initialized.")
            return None
        try:
            # Run the synchronous list_models call in a separate thread
            loop = asyncio.get_event_loop()
            models_iterator = await loop.run_in_executor(None, self.client.models.list)
            
            approved_prefixes = ["gemma", "gemini"]
            models_list = []
            for model in models_iterator: # Iterate over the result from the executor
                model_name = model.name.replace("models/", "")
                if any(model_name.startswith(prefix) for prefix in approved_prefixes):
                    models_list.append(model_name)
            
            models_list.sort() # Sort the list of model names alphabetically
            
            self.logger.info(f"Successfully retrieved {len(models_list)} Gemini models.")
            return models_list
        except Exception as e:
            self.logger.exception(f"Error listing Gemini models: {e}")
            return None

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Gemini provider.
        These should align with SettingsService.DEFAULT_SETTINGS for 'gemini'.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Gemini integration."},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Gemini API key"},
            "model": {"value": "gemini-1.5-flash-latest", "type": SettingType.STRING, "description": "Gemini model name (e.g., gemini-1.5-flash-latest, gemini-1.5-pro-latest)."},
            "thinking_budget": {"value": 1024.0, "type": SettingType.FLOAT, "description": "Gemini thinking budget (0 to disable, min 1024 if enabled, max 24576)."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "Gemini temperature for controlling randomness (e.g., 0.7). Values typically range from 0.0 to 2.0."},
        }

    # Example of a helper for provider-specific kwargs, though not strictly required by base
    # def _get_thinking_budget_from_kwargs(self, **kwargs: Any) -> Optional[float]:
    #     return kwargs.get('thinking_budget')