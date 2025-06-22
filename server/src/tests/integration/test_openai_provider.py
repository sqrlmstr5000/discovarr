import os
import unittest
from typing import Any, Optional, List, Dict

from providers.openai import OpenAIProvider # The class we are testing
from tests.integration.base.base_live_llm_provider_tests import BaseLiveLlmProviderTests # The base test class

# Environment variable names
OPENAI_API_KEY_ENV_VAR = "OPENAI_TEST_API_KEY"
OPENAI_BASE_URL_ENV_VAR = "OPENAI_TEST_BASE_URL"
OPENAI_TEST_MODEL_ENV_VAR = "OPENAI_TEST_MODEL" # Optional, for overriding the default test model
OPENAI_TEST_EMBEDDING_MODEL_ENV_VAR = "OPENAI_TEST_EMBEDDING_MODEL"

# Default model to use for tests if not overridden by environment variable
DEFAULT_OPENAI_TEST_MODEL = "gpt-4o" 
DEFAULT_OPENAI_TEST_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_OPENAI_TEST_EMBEDDING_DIMENSIONS = 1536

class TestOpenAIProviderLive(BaseLiveLlmProviderTests):
    """
    Live integration tests for the OpenAIProvider.
    Requires the OPENAI_API_KEY environment variable to be set.
    """

    def _get_provider_instance(self) -> OpenAIProvider:
        api_key = os.getenv(OPENAI_API_KEY_ENV_VAR)
        base_url = os.getenv(OPENAI_BASE_URL_ENV_VAR) # Can be None, will use provider default
        if not api_key:
            self.skipTest(f"{OPENAI_API_KEY_ENV_VAR} environment variable not set.")
        # If base_url is None, the provider's __init__ will use its default.
        return OpenAIProvider(openai_api_key=api_key, openai_base_url=base_url)

    def _get_model_name(self) -> str:
        return os.getenv(OPENAI_TEST_MODEL_ENV_VAR, DEFAULT_OPENAI_TEST_MODEL)

    def _get_generate_content_prompt_data(self) -> List[Dict[str, str]]:
        """Return a list of messages for OpenAI's _generate_content."""
        return [{'role': 'user', 'content': 'Tell me a short, one-sentence joke.'}]

    def _get_embedding_model_name(self) -> str:
        return os.getenv(OPENAI_TEST_EMBEDDING_MODEL_ENV_VAR, DEFAULT_OPENAI_TEST_EMBEDDING_MODEL)

    def _get_embedding_dimensions(self) -> Optional[int]:
        # text-embedding-3-small can have variable dimensions, but let's test a fixed one.
        return DEFAULT_OPENAI_TEST_EMBEDDING_DIMENSIONS

    def _get_required_env_vars(self) -> list[str]:
        return [OPENAI_API_KEY_ENV_VAR]

if __name__ == '__main__':
    unittest.main()