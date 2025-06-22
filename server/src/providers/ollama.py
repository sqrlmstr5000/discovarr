import json
import logging
import asyncio
from typing import Optional, Dict, Any, List

from ollama import AsyncClient

from services.models import Suggestion, SuggestionList, MediaType
from base.llm_provider_base import LLMProviderBase
from services.models import SettingType # Import SettingType from models

class OllamaProvider(LLMProviderBase):
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

        self.logger.info(f"Initializing Ollama With Base URL: {self.ollama_base_url}")
        try:
            self.client = AsyncClient(host=self.ollama_base_url)
        except Exception as e:
            self.logger.error(f"Failed to initialize Ollama client: {e}")
            self.client = None

    @property
    def name(self) -> str:
        """Returns the name of the LLM provider."""
        return self.PROVIDER_NAME

    async def _generate_content(
        self,
        model: str,
        prompt_data: str, 
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        response_format_details: Optional[Any] = None, # JSON schema for 'format' parameter
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Generates content using the Ollama API.
        """
        if not self.client:
            return {'success': False, 'content': None, 'token_counts': None, 'message': "Ollama client is not initialized."}

        content = None
        content_str = None
        response = None # Initialize response to avoid UnboundLocalError
        options = {}
        if temperature is not None:
            options['temperature'] = temperature

        try:
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt_data}
            ]
            format_param = None
            if response_format_details: # This should be SuggestionList.model_json_schema() or similar
                # Ollama's format parameter expects a dictionary (JSON schema)
                format_param = response_format_details.model_json_schema()

            self.logger.debug(f"Sending request to Ollama model {model} with messages: {prompt_data}")
            response = await self.client.chat(
                model=model,
                messages=messages,
                format=format_param,
                options=options if options else None
            )

            if response_format_details:
                content_str = response['message']['content']
                content = json.loads(content_str)
            else:
                content_str = response['message']['content']
                content = content_str
                
            token_counts = {
                'prompt_token_count': response.get('prompt_eval_count', 0),
                'candidates_token_count': response.get('eval_count', 0),
                'thoughts_token_count': 0, # Ollama doesn't have a direct 'thoughts' token count
                'total_token_count': response.get('prompt_eval_count', 0) + response.get('eval_count', 0),
            }
            return {'success': True, 'content': content, 'token_counts': token_counts}
        except json.JSONDecodeError as e:
            self.logger.debug(f"Ollama raw content for _generate_content: {content_str}")
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"Ollama API returned non-JSON or malformed JSON response: {content_str} - {e}"}
        except Exception as e:
            self.logger.error(f"Ollama API general error: {e}", exc_info=True)
            self.logger.debug(f"Ollama raw response for _generate_content: {response}")
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"Ollama API general error: {e}"}

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
            return {'success': False, 'message': "Ollama client is not initialized.", 'status_code': 500, 'response': None, 'token_counts': None}

        # Ollama chat endpoint usually expects a system message.
        if system_prompt is None:
            system_prompt = "You are a helpful assistant."

        self.logger.debug(f"get_similar_media using prompt: {prompt} and system_prompt: {system_prompt}")

        generation_result = await self._generate_content(
            model=model,
            prompt_data=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format_details=SuggestionList, # Specific schema format for this task
            **kwargs # Pass through other kwargs if any
        )

        if not generation_result['success']:
            self.logger.error(f"Failed to get similar media from Ollama: {generation_result.get('message')}")
            return {'success': False, 'message': generation_result.get('message', 'Generation failed'), 'status_code': 500, 'response': None, 'token_counts': None}

        self.logger.debug(f"Ollama token usage for get_similar_media: {generation_result['token_counts']}")
        return {
            'success': True,
            'response': generation_result['content'], # This is the parsed SuggestionList
            'token_counts': generation_result['token_counts']
        }

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

    async def get_embedding(self, text_content: str, model: Optional[str] = None, dimensions: Optional[int] = None) -> Optional[List[float]]:
        """
        Generates an embedding for the given text content using the specified Ollama model.

        Args:
            text_content (str): The text content to embed.
            model (Optional[str]): The Ollama model to use for embeddings.
                                   If None, a default or configured model might be used
                                   (though current Ollama client requires it).

        Returns:
            Optional[List[float]]: The embedding vector as a list of floats, or None on error.
        """
        if not self.client:
            self.logger.error("Ollama client is not initialized. Cannot get embedding.")
            return None
        if not text_content:
            self.logger.warning("No text content provided for embedding.")
            return None
        if not model: # Ollama's client.embeddings requires a model
            self.logger.error("Ollama model name must be provided for generating embeddings.")
            return None

        try:
            self.logger.debug(f"Requesting embedding for text using Ollama model: {model}")
            response = await self.client.embeddings(model=model, prompt=text_content)
            return response.get('embedding')
        except Exception as e:
            self.logger.error(f"Error generating embedding with Ollama model {model}: {e}", exc_info=True)
            return None
        
    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the Ollama provider.
        These should align with SettingsService.DEFAULT_SETTINGS for 'ollama'.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Ollama integration."},
            "base_url": {"value": "http://ollama:11434", "type": SettingType.URL, "description": "Ollama server base URL (e.g., http://localhost:11434).", "required": True},
            "model": {"value": "llama3", "type": SettingType.STRING, "description": "Ollama model name to use (e.g., llama3, mistral)."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "Ollama temperature for controlling randomness (e.g., 0.7). Higher values mean more random."},
            "embedding_model": {"value": "nomic-embed-text", "type": SettingType.STRING, "show": False, "description": "Ollama model name to use for embeddings (e.g., nomic-embed-text, mxbai-embed-large). Leave blank to disable Ollama embeddings."},
            "embedding_dimensions": {"value": 768, "type": SettingType.INTEGER, "show": False, "description": "Number of dimensions for model embeddings. The size is determined by the model used, e.g., 768 for nomic-embed-text. https://github.com/ollama/ollama/issues/651"},
            "base_provider": {"value": "llm", "type": SettingType.STRING, "show": False, "description": "Base Provider Type"},
        }