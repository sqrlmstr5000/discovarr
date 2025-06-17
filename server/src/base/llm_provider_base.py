from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

class LLMProviderBase(ABC):
    """
    Abstract base class for LLM providers.
    Defines a common interface for interacting with different LLM services.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the LLM provider (e.g., "Gemini", "Ollama").
        """
        pass

    @abstractmethod
    async def get_similar_media(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Generates media suggestions based on a prompt.

        Args:
            model (str): The specific model to use for this LLM provider.
            prompt (str): The user's prompt for suggestions.
            system_prompt (Optional[str]): System instructions for the LLM.
            temperature (Optional[float]): Controls randomness.
            **kwargs: Additional provider-specific parameters (e.g., thinking_budget for Gemini).

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the LLM's response
                                      and token counts, or None on error.
                                      Expected structure:
                                      {
                                          'response': Dict[str, Any],  # Parsed LLM output
                                          'token_counts': Dict[str, int] # Token usage
                                      }
        """
        pass

    @abstractmethod
    async def _generate_content(
        self,
        model: str,
        prompt_data: Any,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        response_format_details: Optional[Any] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Low-level content generation method to be implemented by each provider.

        Args:
            model (str): The specific model to use.
            prompt_data (Any): Provider-specific prompt input (e.g., string, list of messages).
            system_prompt (Optional[str]): System instructions for the LLM.
            temperature (Optional[float]): Controls randomness.
            response_format_details (Optional[Any]): Provider-specific details for response formatting (e.g., Pydantic model, JSON schema).
            **kwargs: Additional provider-specific parameters.

        Returns:
            Dict[str, Any]: A dictionary containing 'success' (bool), 'content' (Any), 'token_counts' (Optional[Dict]), and 'message' (Optional[str]).
        """
        pass

    @abstractmethod
    async def get_models(self) -> Optional[List[str]]:
        """
        Lists available model names for this LLM provider.

        Returns:
            Optional[List[str]]: A list of model names, or None on error.
        """
        pass

    @abstractmethod
    async def get_embedding(self, text_content: str, model: Optional[str] = None, dimensions: Optional[int] = None) -> Optional[List[float]]:
        """
        Generates an embedding for the given text using the LLM provider's embedding model.

        Args:
            text_content (str): The text to embed.

        Returns:
            Optional[List[float]]: A list of floats representing the embedding, or None on error.
        """
        pass

    @classmethod
    @abstractmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns the default settings specific to this LLM provider.
        This method should be implemented by each concrete provider class.
        The structure should align with how settings are defined in SettingsService.
        """
        pass
