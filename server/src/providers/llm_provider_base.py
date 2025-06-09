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
    async def get_models(self) -> Optional[List[str]]:
        """
        Lists available model names for this LLM provider.

        Returns:
            Optional[List[str]]: A list of model names, or None on error.
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
