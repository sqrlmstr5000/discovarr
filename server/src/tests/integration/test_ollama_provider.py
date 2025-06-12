import os
import unittest
from typing import Any

from providers.ollama import OllamaProvider # The class we are testing
from tests.integration.base.base_live_llm_provider_tests import BaseLiveLlmProviderTests # The base test class

# Environment variable names
OLLAMA_TEST_BASE_URL_ENV_VAR = "OLLAMA_TEST_BASE_URL"
OLLAMA_TEST_MODEL_ENV_VAR = "OLLAMA_TEST_MODEL" # Optional, for overriding the default test model

# Default model to use for tests if not overridden by environment variable
# Using the default from OllamaProvider.get_default_settings()
DEFAULT_OLLAMA_TEST_MODEL = "llama3" 

class TestOllamaProviderLive(BaseLiveLlmProviderTests):
    """
    Live integration tests for the OllamaProvider.
    Requires the OLLAMA_TEST_BASE_URL environment variable to be set.
    Optionally, OLLAMA_TEST_MODEL can be set to use a specific model for testing.
    """

    def _get_provider_instance(self) -> OllamaProvider:
        base_url = os.getenv(OLLAMA_TEST_BASE_URL_ENV_VAR)
        if not base_url:
            self.skipTest(f"{OLLAMA_TEST_BASE_URL_ENV_VAR} environment variable not set.")
        
        # OllamaProvider constructor takes ollama_base_url
        return OllamaProvider(ollama_base_url=base_url)

    def _get_model_name(self) -> str:
        return os.getenv(OLLAMA_TEST_MODEL_ENV_VAR, DEFAULT_OLLAMA_TEST_MODEL)

    def _get_required_env_vars(self) -> list[str]:
        return [OLLAMA_TEST_BASE_URL_ENV_VAR]

    # BaseLiveLlmProviderTests provides:
    # - asyncSetUp
    # - test_get_models_live
    # - test_get_similar_media_live_basic 
    #   (OllamaProvider.get_similar_media returns a dict matching SuggestionList, so this should pass)
    # - test_get_similar_media_live_with_suggestion_list_schema
    #   (OllamaProvider.get_similar_media uses SuggestionList schema by default)

if __name__ == '__main__':
    # This allows running the tests directly from this file:
    # python -m tests.integration.plugins.test_ollama_provider
    unittest.main()