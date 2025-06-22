import json
import logging
from typing import Optional, Dict, Any, List, Union
from openai import AsyncOpenAI
from pydantic import BaseModel

from base.llm_provider_base import LLMProviderBase
from services.models import SuggestionList, SettingType

class OpenAIProvider(LLMProviderBase):
    """
    A class to interact with the OpenAI API for finding similar media.
    Conforms to the LLMProviderBase interface.
    """
    PROVIDER_NAME = "openai"

    def __init__(self, api_key: str, base_url: Optional[str] = "https://api.openai.com/v1"):
        """
        Initializes the OpenAIProvider with API configurations.

        Args:
            openai_api_key (str): The OpenAI API key.
            openai_base_url (Optional[str]): The base URL for the OpenAI API.
                                             Defaults to "https://api.openai.com/v1".
        """
        self.logger = logging.getLogger(__name__)
        self.openai_api_key = api_key
        self.logger.info("Initializing OpenAIProvider...")

        if not self.openai_api_key:
            self.logger.error("OpenAI API Key is not configured. Cannot initialize client.")
            self.client = None
            return

        self.client = AsyncOpenAI(api_key=self.openai_api_key, base_url=base_url)

    @property
    def name(self) -> str:
        """Returns the name of the LLM provider."""
        return self.PROVIDER_NAME

    async def _generate_content(
        self,
        model: str,
        prompt_data: Union[str, List[Dict[str, str]]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        response_format_details: Optional[Any] = None, # Pydantic model for response_model
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Generates content using the OpenAI API.
        """
        if not self.client:
            return {'success': False, 'content': None, 'token_counts': None, 'message': "OpenAI client is not initialized."}

        messages = []
        if isinstance(prompt_data, str):
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt_data})
        elif isinstance(prompt_data, list):
            messages = prompt_data
            if system_prompt:
                self.logger.warning("system_prompt was provided to _generate_content along with a list of messages. Ignoring the system_prompt argument as the list is expected to be complete.")
        else:
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"Invalid prompt_data format for OpenAI: {type(prompt_data)}"}

        try:
            self.logger.debug(f"Sending request to OpenAI model {model} with messages: {messages}")
            
            usage = None
            response = None
            content_str = None
            if response_format_details:
                # This assumes a library like 'instructor' is used to patch the client for 'response_model'
                chat_completion_kwargs = {
                    "model": model,
                    "input": messages,
                    "temperature": temperature,
                    "text_format": response_format_details,
                }
                self.logger.debug(f"OpenAI kwargs for _generate_content: {chat_completion_kwargs}")
                response = await self.client.responses.parse(**chat_completion_kwargs)
                content_str = response.output[0].content[0].text
                content = json.loads(content_str)
                usage = response.usage
            else:
                chat_completion_kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                self.logger.debug(f"OpenAI kwargs for _generate_content: {chat_completion_kwargs}")
                response = await self.client.chat.completions.create(**chat_completion_kwargs)
                content_str = response.choices[0].message.content
                content = content_str
                usage = response.usage

            token_counts = None
            if usage:
                self.logger.debug(f"OpenAI raw token usage for _generate_content: {usage}")
                token_counts = {
                    'prompt_token_count': getattr(usage, 'input_tokens', getattr(usage, 'prompt_tokens', 0)),
                    'candidates_token_count': getattr(usage, 'output_tokens', getattr(usage, 'completion_tokens', 0)),
                    'thoughts_token_count': 0, # OpenAI doesn't have a direct 'thoughts' token count
                    'total_token_count': usage.total_tokens,
                }
                self.logger.debug(f"OpenAI token usage for _generate_content: {token_counts}")
            return {'success': True, 'content': content, 'token_counts': token_counts}
        except json.JSONDecodeError as e:
            self.logger.debug(f"OpenAI raw content for _generate_content: {content_str}")
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"OpenAI API returned non-JSON or malformed JSON response: {content_str} - {e}"}
        except Exception as e:
            self.logger.error(f"OpenAI API general error: {e}", exc_info=True)
            self.logger.debug(f"OpenAI raw response for _generate_content: {response}")
            return {'success': False, 'content': None, 'token_counts': None, 'message': f"OpenAI API general error: {e}"}

    async def get_similar_media(self, model: str, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = 0.7, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Uses the OpenAI API to find media similar to the user's prompt, returning structured JSON.
        """
        if not self.client:
            self.logger.error("OpenAI client is not initialized.")
            return {'success': False, 'message': "OpenAI client is not initialized.", 'status_code': 500}

        if system_prompt is None:
            system_prompt = "You are a helpful assistant."

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt}
        ]

        self.logger.debug(f"get_similar_media using prompt: {prompt} and system_prompt: {system_prompt}")

        generation_result = await self._generate_content(
            model=model,
            prompt_data=messages,
            temperature=temperature,
            response_format_details=SuggestionList, # Pass the Pydantic model to indicate JSON output is desired
            **kwargs
        )

        if not generation_result['success']:
            self.logger.error(f"Failed to get similar media from OpenAI: {generation_result.get('message')}")
            return {'success': False, 'message': generation_result.get('message', 'Generation failed'), 'status_code': 500}

        return {
            'success': True,
            'response': generation_result['content'], # This is the parsed SuggestionList
            'token_counts': generation_result['token_counts']
        }

    async def get_models(self) -> Optional[List[str]]:
        """Lists available model names from the OpenAI API."""
        if not self.client:
            self.logger.error("OpenAI client is not initialized.")
            return None
        try:
            models_page = await self.client.models.list()
            # Filter for models that can be used with the Chat Completions API
            approved_prefixes = ["gpt-4", "gpt-3.5"]
            models_list = sorted([
                model.id for model in models_page.data 
                if any(model.id.startswith(prefix) for prefix in approved_prefixes)
            ])
            self.logger.info(f"Successfully retrieved {len(models_list)} OpenAI models.")
            return models_list
        except Exception as e:
            self.logger.exception(f"Error listing OpenAI models: {e}")
            return None

    async def get_embedding(self, text_content: str, model: Optional[str] = None, dimensions: Optional[int] = None) -> Optional[List[float]]:
        """
        Generates an embedding for the given text content using the specified OpenAI model.

        Args:
            text_content (str): The text to embed.
            model (Optional[str]): The OpenAI model to use for embeddings.
            dimensions (Optional[int]): The number of dimensions for the embedding.

        Returns:
            Optional[List[float]]: A list of floats representing the embedding, or None on error.
        """
        if not self.client:
            self.logger.error("OpenAI client is not initialized. Cannot get embedding.")
            return None
        if not text_content:
            self.logger.warning("No text content provided for embedding.")
            return None
        if not model:
            self.logger.error("OpenAI model name must be provided for generating embeddings.")
            return None

        try:
            self.logger.debug(f"Requesting embedding for text using OpenAI model: {model}")
            embedding_params = {"model": model, "input": text_content}
            if dimensions:
                embedding_params["dimensions"] = dimensions
            
            response = await self.client.embeddings.create(**embedding_params)
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Error generating embedding with OpenAI model {model}: {e}", exc_info=True)
            return None

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings for the OpenAI provider.
        """
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable OpenAI integration."},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "OpenAI API key", "required": True},
            "base_url": {"value": "https://api.openai.com/v1", "type": SettingType.URL, "description": "OpenAI compatible API base URL.", "required": True},
            "model": {"value": "gpt-4.1-mini", "type": SettingType.STRING, "description": "OpenAI model name (e.g., gpt-4o, gpt-4-turbo)."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "OpenAI temperature for controlling randomness (e.g., 0.7). Values range from 0.0 to 2.0."},
            "embedding_model": {"value": "text-embedding-3-small", "type": SettingType.STRING, "show": False, "description": "OpenAI model name to use for embeddings (e.g., text-embedding-3-small, text-embedding-3-large)."},
            "embedding_dimensions": {"value": 1536, "type": SettingType.INTEGER, "show": False, "description": "Number of dimensions for OpenAI embeddings (e.g., 1536 for text-embedding-3-small)."},
            "base_provider": {"value": "llm", "type": SettingType.STRING, "show": False, "description": "Base Provider Type"},
        }
