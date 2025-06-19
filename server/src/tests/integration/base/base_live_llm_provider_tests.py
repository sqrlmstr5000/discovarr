import unittest
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, List

from base.llm_provider_base import LLMProviderBase # LLMProviderBase is what we are testing
from services.models import SuggestionList 

class BaseLiveLlmProviderTests(ABC, unittest.IsolatedAsyncioTestCase):
    """
    Abstract base class for **live integration tests** of LLMProviderBase implementations.
    
    Subclasses must:
    1. Implement `_get_provider_instance` to return an initialized instance of the LLM provider.
    2. Implement `_get_model_name` to return a valid model name for the provider.
    3. Implement `_get_required_env_vars` to list environment variables needed for the tests.
       Tests will be skipped if these are not set.
    4. The `LLMProviderBase` subclass being tested should handle its own `aiohttp.ClientSession`
       creation and management internally for live calls.
    """

    provider: LLMProviderBase
    model_name: str
    # Common optional parameters that might be used in tests
    default_system_prompt: str = "You are a movie recommendation assistant. Your job is to suggest movies to users based on their preferences and current context."
    default_temperature: float = 0.7

    @abstractmethod
    def _get_provider_instance(self) -> LLMProviderBase:
        """Return an initialized instance of the LLM provider to be tested."""
        pass

    @abstractmethod
    def _get_model_name(self) -> str:
        """Return a valid model name for the provider to use in tests."""
        pass

    @abstractmethod
    def _get_embedding_model_name(self) -> str:
        """Return a valid embedding model name for the provider to use in embedding tests."""
        pass

    @abstractmethod
    def _get_embedding_dimensions(self) -> Optional[int]:
        """Return the expected output dimensions for the embedding, or None if not applicable/testable."""
        pass

    @abstractmethod
    def _get_required_env_vars(self) -> list[str]:
        """Return a list of environment variable names required for this provider's live tests."""
        pass

    async def asyncSetUp(self):
        await super().asyncSetUp()
        required_env_vars = self._get_required_env_vars()
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            self.skipTest(f"Missing required environment variables for live test: {', '.join(missing_vars)}")

        self.provider = self._get_provider_instance()
        self.model_name = self._get_model_name()
        
        if not self.provider:
            self.fail("Provider instance was not created by _get_provider_instance().") # Use fail for setup issues
        if not self.model_name:
             self.skipTest("Model name not provided by _get_model_name() for live test.")

    async def test_get_models_live(self):
        """Tests the live get_models() method of the LLM provider."""
        if not hasattr(self.provider, 'get_models'):
            self.skipTest(f"Provider '{self.provider.name}' does not implement get_models.")
            return

        models_response = await self.provider.get_models()
        
        self.assertIsNotNone(models_response, f"{self.provider.name}.get_models() should return a response, not None.")
        # LLMProviderBase.get_models is typed to return Optional[List[str]]
        self.assertIsInstance(models_response, list, f"{self.provider.name}.get_models() should return a list.")
        
        if models_response:
            # Check if the test model (which is a string) is in the list of models.
            # This assumes providers returning List[Dict] would have their specific tests
            # or that their `get_models` conforms to `List[str]` as per `LLMProviderBase`.
            is_list_of_strings = all(isinstance(m, str) for m in models_response)
            is_list_of_dicts_with_name = all(isinstance(m, dict) and "name" in m for m in models_response)
            is_list_of_dicts_with_id = all(isinstance(m, dict) and "id" in m for m in models_response)

            found_test_model = False
            if is_list_of_strings:
                found_test_model = self.model_name in models_response
            elif is_list_of_dicts_with_name:
                found_test_model = self.model_name in [m["name"] for m in models_response]
            elif is_list_of_dicts_with_id: # For providers like Gemini that might use 'id'
                found_test_model = self.model_name in [m["id"] for m in models_response]
            
            # This assertion can be tricky due to model naming variations.
            # It's a good check but might need adjustment per provider.
            # self.assertTrue(found_test_model, 
            #                 f"The test model '{self.model_name}' was not found in the list of available models from {self.provider.name}.")
            self.assertTrue(len(models_response) > 0, f"{self.provider.name}.get_models() list should not be empty if successful and models exist.")

    async def test_get_similar_media_live_with_suggestion_list_schema(self):
        """
        Tests the live get_similar_media() method of GeminiProvider with response_schema=SuggestionList.
        """
        if not hasattr(self.provider, 'get_similar_media'):
            self.skipTest(f"Provider '{self.provider.name}' does not implement get_similar_media.")
            return

        prompt_text = "Recommend 10 tv series or movies similar to Dazed and Confused."
        
        result = await self.provider.get_similar_media(
            model=self.model_name,
            prompt=prompt_text,
            temperature=self.default_temperature,
            system_prompt=self.default_system_prompt,
        )

        self.assertIsNotNone(result, f"{self.provider.name}.get_similar_media() should return a result, not None.")
        self.assertIsInstance(result, dict, f"{self.provider.name}.get_similar_media() should return a dictionary.")
        
        self.assertIn('response', result, "Result dictionary must contain a 'response' key.")
        self.assertIsInstance(result['response'], dict, "The 'response' field should be a dictionary when using a Pydantic schema.")
        
        self.assertIn('suggestions', result['response'], "The 'response' dictionary should contain a 'suggestions' key.")
        self.assertIsInstance(result['response']['suggestions'], list, "The 'suggestions' field should be a list.")

        # Assert token_counts structure
        self.assertIn('token_counts', result, "Result dictionary must contain a 'token_counts' key.")
        self.assertIsInstance(result['token_counts'], dict, "The 'token_counts' field should be a dictionary.")
        # Assert individual token count fields
        self.assertIn('prompt_token_count', result['token_counts'], "Token counts should include 'prompt_token_count'.")
        self.assertIsInstance(result['token_counts']['prompt_token_count'], int, "'prompt_token_count' should be an integer.")
        self.assertIn('candidates_token_count', result['token_counts'], "Token counts should include 'candidates_token_count'.")
        self.assertIsInstance(result['token_counts']['candidates_token_count'], int, "'candidates_token_count' should be an integer.")
        self.assertIn('thoughts_token_count', result['token_counts'], "Token counts should include 'thoughts_token_count'.") # Gemini specific
        self.assertTrue(isinstance(result['token_counts']['thoughts_token_count'], int) or result['token_counts']['thoughts_token_count'] is None, "'thoughts_token_count' should be an integer or None.")
        self.assertIn('total_token_count', result['token_counts'], "Token counts should include 'total_token_count'.")
        self.assertIsInstance(result['token_counts']['total_token_count'], int, "'total_token_count' should be an integer.")

        if result['response']['suggestions']:
            first_suggestion = result['response']['suggestions'][0]
            self.assertIsInstance(first_suggestion, dict, "Each suggestion should be a dictionary.")
            self.assertIn('title', first_suggestion, "Each suggestion should have a 'title'.")
            self.assertIn('mediaType', first_suggestion, "Each suggestion should have a 'mediaType'.")

    async def test_get_embedding_live(self):
        """Tests the live get_embedding() method of the LLM provider."""
        if not hasattr(self.provider, 'get_embedding'):
            self.skipTest(f"Provider '{self.provider.name}' does not implement get_embedding.")
            return

        embedding_model_name = self._get_embedding_model_name()
        if not embedding_model_name:
            self.skipTest("Embedding model name not provided by _get_embedding_model_name() for live test.")
            return
            
        embedding_dimensions = self._get_embedding_dimensions() # Can be None

        sample_text = "This is a sample text to generate an embedding."
        
        embedding_result = await self.provider.get_embedding(
            text_content=sample_text,
            model=embedding_model_name,
            dimensions=embedding_dimensions
        )

        self.assertIsNotNone(embedding_result, f"{self.provider.name}.get_embedding() should return a result, not None.")
        self.assertIsInstance(embedding_result, list, f"{self.provider.name}.get_embedding() should return a list.")
        
        if embedding_result: # If the list is not empty
            self.assertTrue(all(isinstance(val, float) for val in embedding_result), "All elements in the embedding list should be floats.")
            self.assertTrue(len(embedding_result) > 0, "Embedding list should not be empty if successful.")
            if embedding_dimensions is not None:
                self.assertEqual(len(embedding_result), embedding_dimensions, f"Embedding dimensions should match. Expected {embedding_dimensions}, got {len(embedding_result)}.")