import json
import logging
import asyncio
from typing import Optional, Dict, Any, List

import ollama # Official Ollama client

from .models import Suggestion, SuggestionList, MediaType

class Ollama:
    """
    A class to interact with the Ollama API for finding similar media and listing models.
    """

    def __init__(self, ollama_base_url: str):
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

    async def get_similar_media(self, model: str, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = 0.7) -> Optional[Dict[str, Any]]:
        """
        Uses the Ollama API to find media similar to the user's prompt, returning structured JSON.

        Args:
            prompt (str): The user's request/prompt.
            system_prompt (Optional[str]): Base system instructions for the AI.
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