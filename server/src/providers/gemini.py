import json
import logging
import sys  
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import asyncio # For running sync code in async
from google import genai
from google.genai import types
from services.models import SuggestionList
from base.llm_provider_base import LLMProviderBase
from services.models import SettingType # Import SettingType from models

class GeminiProvider(LLMProviderBase):
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

    async def _generate_content(
        self,
        model: str,
        prompt_data: str, # For Gemini, prompt_data is a string
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        response_format_details: Optional[Any] = None, # Pydantic model for response_schema
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Generates content using the Gemini API.
        """
        if not self.gemini_api_key:
            return {'success': False, 'content': None, 'token_counts': None, 'message': "Gemini API Key is not configured."}

        config_params = {
            "system_instruction": system_prompt,
            "temperature": temperature,
        }
        if response_format_details: # This should be a Pydantic model for Gemini
            config_params["response_mime_type"] = "application/json"
            config_params["response_schema"] = response_format_details

        thinking_config_param = None
        thinking_budget_kwarg = kwargs.get('thinking_budget')
        # Check if model supports thinking_config (e.g., 1.5 series)
        if "2.5-pro" in model or "2.5-flash" in model: # Adjusted model check
            if thinking_budget_kwarg is not None:
                try:
                    tb_float = float(thinking_budget_kwarg)
                    if tb_float > 0: # Assuming 0 or negative means disable
                        thinking_config_param = types.ThinkingConfig(thinking_budget=tb_float)
                        self.logger.debug(f"Applying thinking_budget {tb_float} for model {model}.")
                    else:
                        self.logger.debug(f"Thinking_budget is {tb_float}, not applying thinking_config for model {model}.")
                except ValueError:
                    self.logger.warning(f"Invalid thinking_budget value '{thinking_budget_kwarg}' for model {model}. Disabling thinking_config.")
        
        if thinking_config_param:
            config_params["thinking_config"] = thinking_config_param

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=prompt_data, # 'contents' takes the string prompt
                config=types.GenerateContentConfig(**config_params)
            )
            if response_format_details: # This should be a Pydantic model for Gemini
                content = json.loads(response.text) # Parsed content based on response_schema
            else:
                content = response.text # Return raw text if no schema is provided

            usage_meta = response.usage_metadata
            token_counts = {
                'prompt_token_count': usage_meta.prompt_token_count,
                'candidates_token_count': usage_meta.candidates_token_count,
                'thoughts_token_count': usage_meta.thoughts_token_count,
                'total_token_count': usage_meta.total_token_count,
            }
            return {'success': True, 'content': content, 'token_counts': token_counts}
        except json.JSONDecodeError as e:
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"Gemini API returned non-JSON or malformed JSON response: {response.text if 'response' in locals() else 'Response object not available'} - {e}"}
        except Exception as e:
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"Gemini API general error: {e}"}

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
            return {'success': False, 'message': "Gemini API Key is not configured.", 'status_code': 500}

        self.logger.debug(f"get_similar_media using prompt: {prompt}")

        generation_result = await self._generate_content(
            model=model,
            prompt_data=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format_details=SuggestionList, # Specific Pydantic model for this task
            thinking_budget=kwargs.get('thinking_budget') 
        )

        if not generation_result['success']:
            self.logger.error(f"Failed to get similar media from Gemini: {generation_result.get('message')}")
            return {'success': False, 'message': generation_result.get('message', 'Generation failed'), 'status_code': 500}

        self.logger.debug(f"Gemini token usage for get_similar_media: {generation_result['token_counts']}")
        return {
            'success': True,
            'response': generation_result['content'], # This is the parsed SuggestionList
            'token_counts': generation_result['token_counts']
        }

    async def get_embedding(self, text_content: str, model: Optional[str] = None, dimensions: Optional[int] = None) -> Optional[List[float]]:
        """
        Generates an embedding for the given text content using a specific Gemini embedding model.

        Args:
            text_content (str): The text content to embed.

        Returns:
            Optional[List[float]]: The embedding vector as a list of floats, or None on error.
        """
        if not self.client:
            self.logger.error("Gemini client is not initialized. Cannot get embedding.")
            return None
        if not text_content:
            self.logger.warning("No text content provided for embedding.")
            return None

        embedding_model = model # Or "models/text-embedding-004" / "models/text-embedding-preview-0409"
        # The model "gemini-embedding-exp-03-07" seems experimental or internal.
        # Using a generally available embedding model like "models/embedding-001".
        # Refer to https://ai.google.dev/gemini-api/docs/models/gemini for current embedding models.

        try:
            self.logger.debug(f"Requesting embedding for text using model: {embedding_model}")
            result = await self.client.aio.models.embed_content(model=embedding_model, 
                                                                contents=text_content,
                                                                config=types.EmbedContentConfig(
                                                                    output_dimensionality=dimensions),
                                                                    task_type="SEMANTIC_SIMILARITY")
            return result.embeddings[0].values
        except Exception as e:
            self.logger.error(f"Error generating embedding with Gemini model {embedding_model}: {e}", exc_info=True)
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
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Gemini API key", "required": True},
            "model": {"value": "gemini-2.5-flash-preview-05-20", "type": SettingType.STRING, "description": "Gemini model name (e.g., gemini-1.5-flash-latest, gemini-1.5-pro-latest)."},
            "thinking_budget": {"value": 1024.0, "type": SettingType.FLOAT, "description": "Gemini thinking budget (0 to disable, min 1024 if enabled, max 24576)."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "Gemini temperature for controlling randomness (e.g., 0.7). Values typically range from 0.0 to 2.0."},
            "embedding_model": {"value": "gemini-embedding-exp", "type": SettingType.STRING, "show": False, "description": "Gemini model name to use for embeddings (e.g., gemini-embedding-exp)."},
            "embedding_dimensions": {"value": 768, "type": SettingType.INTEGER, "show": False, "description": "Number of dimensions for Gemini embeddings (max: 3072). Higher dimensions may improve quality but increase cost and storage requirements."},
            "base_provider": {"value": "llm", "type": SettingType.STRING, "show": False, "description": "Base Provider Type"},
        }

    # Example of a helper for provider-specific kwargs, though not strictly required by base
    # def _get_thinking_budget_from_kwargs(self, **kwargs: Any) -> Optional[float]:
    #     return kwargs.get('thinking_budget')