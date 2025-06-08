import json
import logging
import asyncio
from typing import Optional, Dict, Any, List

import ollama # Official Ollama client

from .models import Suggestion, SuggestionList, MediaType
from .llm_provider_base import LLMProviderBase
from .models import SettingType # Import SettingType from models

class Ollama(LLMProviderBase):
    """
    A class to interact with the Ollama API for finding similar media and listing models.
    """
    PROVIDER_NAME = "ollama"
    def __init__(self, ollama_base_url: str, **kwargs: Any): # Added **kwargs for future flexibility
        """
        Initializes the Ollama class with API configurations.

        Args:
            ollama_model (str): The Ollama model to use (e.g., "llama3", "mistral").
            ollama_base_url (str): The base URL of the Ollama server (e.g., "http://localhost:11434").
        """
        self.logger = logging.getLogger(__name__)
        self.ollama_base_url = ollama_base_url

        if not self.ollama_base_url:
            self.logger.error("Ollama base URL is not configured. Cannot initialize client.")
            self.client = None
            return

        self.logger.info(f"Initializing Ollama class URL: {self.ollama_base_url}")
        try:
            self.client = ollama.AsyncClient(host=self.ollama_base_url)
        except Exception as e:
            self.logger.error(f"Failed to initialize Ollama client: {e}")
            self.client = None

    @property
    def name(self) -> str:
        """Returns the name of the LLM provider."""
        return self.PROVIDER_NAME

    async def get_similar_media(self, model: str, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = 0.7, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Uses the Ollama API to find media similar to the user's prompt, returning structured JSON.

        Args:
            model (str): The Ollama model to use.
            prompt (str): The user's request/prompt.
            system_prompt (Optional[str]): Base system instructions for the AI.
            temperature (Optional[float]): Controls randomness. Higher is more random.
            **kwargs: Additional provider-specific parameters (ignored by Ollama for this method).
            temperature (Optional[float]): Controls randomness. Higher is more random.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing:
                - 'response': The Ollama API response (parsed JSON list of suggestions).
                - 'token_counts': Dictionary with token usage statistics.
                Or None on error.
        """
        if not self.client:
            self.logger.error("Ollama client is not initialized.")
            return None

        # Ollama chat endpoint usually expects a system message.
        if system_prompt is None:
            system_prompt = "You are a helpful assistant."

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt}
        ]

        try:
            self.logger.debug(f"Sending request to Ollama model {model} with prompt: {prompt}")
            self.logger.debug(f"System prompt for Ollama: {system_prompt}")

            response = await self.client.chat(
                model=model,
                messages=messages,
                format=SuggestionList.model_json_schema(),  
                options={'temperature': temperature} if temperature is not None else None
            )

            ollama_response_content = response['message']['content']
            parsed_json_response = json.loads(ollama_response_content)

            token_counts = {
                'prompt_token_count': response.get('prompt_eval_count', 0),
                'candidates_token_count': response.get('eval_count', 0), # Ollama calls this eval_count
                'thoughts_token_count': 0, # Ollama doesn't have a direct 'thoughts' token count
                'total_token_count': response.get('prompt_eval_count', 0) + response.get('eval_count', 0),
            }
            self.logger.debug(f"Ollama token usage: {token_counts}")

            return {
                'response': parsed_json_response,
                'token_counts': token_counts
            }
        except json.JSONDecodeError:
            self.logger.error(f"Ollama API returned non-JSON or malformed JSON response: {ollama_response_content}")
            return None
        except Exception as e:
            self.logger.exception(f"Ollama API error: {e}")
            return None

    async def get_models(self) -> Optional[List[str]]:
        """Lists available models from the Ollama server."""
        if not self.client:
            self.logger.error("Ollama client is not initialized.")
            return None
        try:
            response = await self.client.list()
            self.logger.debug(f"Ollama response: {response}")
            self.logger.debug(f"Ollama models: {response.get('models', [])}")
            models_list = sorted([model['model'] for model in response.get('models', [])])
            self.logger.info(f"Successfully retrieved {len(models_list)} Ollama models.")
            return models_list
        except Exception as e:
            self.logger.exception(f"Error listing Ollama models: {e}")
            return None

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Ollama provider.
        These should align with SettingsService.DEFAULT_SETTINGS for 'ollama'.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Ollama integration."},
            "base_url": {"value": "http://localhost:11434", "type": SettingType.URL, "description": "Ollama server base URL (e.g., http://localhost:11434)."},
            "model": {"value": "llama3", "type": SettingType.STRING, "description": "Ollama model name to use (e.g., llama3, mistral)."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "Ollama temperature for controlling randomness (e.g., 0.7). Higher values mean more random."},
        }