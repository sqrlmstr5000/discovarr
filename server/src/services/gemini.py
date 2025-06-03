import json
import logging
import sys  
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import asyncio # For running sync code in async
from google import genai
from google.genai import types
from .models import Suggestion, SuggestionList

class Gemini:
    """
    A class to interact with the Gemini API for finding similar media.
    """

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

    async def get_similar_media(self, model: str, prompt: str, system_prompt: Optional[str] = None, thinking_budget: Optional[float] = 0.0, temperature: Optional[float] = 0.7) -> Optional[Dict[str, Any]]:
        """
        Uses the Gemini API to find media similar to the given media name.

        Rate limits for the Gemini API can be found here:
        https://ai.google.dev/gemini-api/docs/rate-limits#current-rate-limits

        Args:
            media_name (str): The name of the movie or TV show.
            media_exclude (str): Media titles to exclude from recommendations
            limit (str): Number of recommendations to request
            custom_prompt (Optional[str]): Optional custom prompt to use

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing:
                - 'response': The Gemini API response
                - 'token_counts': Dictionary with token usage statistics
                Or None on error
        """
        if not self.gemini_api_key:
            self.logger.error("Gemini API Key is not configured.")
            return None

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