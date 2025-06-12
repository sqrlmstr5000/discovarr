import os
import unittest
from typing import Any

from providers.gemini import GeminiProvider # The class we are testing
from tests.integration.base.base_live_llm_provider_tests import BaseLiveLlmProviderTests # The base test class

from services.models import SuggestionList 
# Environment variable names
GEMINI_API_KEY_ENV_VAR = "GEMINI_TEST_API_KEY"
GEMINI_TEST_MODEL_ENV_VAR = "GEMINI_TEST_MODEL" # Optional, for overriding the default test model

# Default model to use for tests if not overridden by environment variable
# Using the default from GeminiProvider.get_default_settings()
DEFAULT_GEMINI_TEST_MODEL = "gemini-2.5-flash-preview-04-17"

class TestGeminiProviderLive(BaseLiveLlmProviderTests):
    """
    Live integration tests for the GeminiProvider.
    Requires the GEMINI_API_KEY environment variable to be set.
    Optionally, GEMINI_TEST_MODEL can be set to use a specific model for testing.
    """

    def _get_provider_instance(self) -> GeminiProvider:
        api_key = os.getenv(GEMINI_API_KEY_ENV_VAR)
        # The asyncSetUp in BaseLiveLlmProviderTests will skip if api_key is None
        # based on _get_required_env_vars, so direct check here is mostly a safeguard.
        if not api_key:
            self.skipTest(f"{GEMINI_API_KEY_ENV_VAR} environment variable not set.")
        return GeminiProvider(gemini_api_key=api_key)

    def _get_model_name(self) -> str:
        return os.getenv(GEMINI_TEST_MODEL_ENV_VAR, DEFAULT_GEMINI_TEST_MODEL)

    def _get_required_env_vars(self) -> list[str]:
        return [GEMINI_API_KEY_ENV_VAR]

    # BaseLiveLlmProviderTests provides:
    # - asyncSetUp
    # - test_get_models_live
    # - test_get_similar_media_live_basic

if __name__ == '__main__':
    # This allows running the tests directly from this file:
    # python -m tests.unit.plugins.test_gemini_provider
    unittest.main()