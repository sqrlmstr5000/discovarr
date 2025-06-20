from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any, Union
from services.models import ItemsFiltered, LibraryUser

class LibraryProviderBase(ABC):
    """
    Abstract base class for media library providers (e.g., Jellyfin, Plex).
    Defines a common interface for interacting with different library services.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the library provider (e.g., "jellyfin", "plex").
        """
        pass

    @abstractmethod
    def get_users(self) -> Optional[List[LibraryUser]]:
        """
        Retrieves all users from the library provider.

        Returns:
            Optional[List[LibraryUser]]: A list of user objects,
                                             or None if an error occurs.
        """
        pass

    @abstractmethod
    def get_user_by_name(self, username: str) -> Optional[LibraryUser]:
        """
        Retrieves a specific user by their username.

        Args:
            username (str): The username to search for.

        Returns:
            Optional[LibraryUser]: The user object if found,
                                       or None otherwise.
        """
        pass

    @abstractmethod
    def get_recently_watched(self, user_id: str, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """
        Retrieves recently watched items for a specific user.

        Args:
            user_id (str): The unique identifier for the user.
            limit (Optional[int]): The maximum number of items to retrieve.

        Returns:
            Optional[List[Dict[str, Any]]]: A list of recently watched items (raw dictionaries),
                                             or None if an error occurs.
        """
        pass

    @abstractmethod
    def get_favorites(self, user_id: str, limit: Optional[int] = None) -> Optional[List[ItemsFiltered]]:
        """
        Retrieves favorite items for a specific user.

        Args:
            user_id (str): The unique identifier for the user.
            limit (Optional[int]): The maximum number of items to retrieve.

        Returns:
            Optional[List[Dict[str, Any]]]: A list of favorite items (raw dictionaries),
                                             or None if an error occurs.
        """
        pass

    @abstractmethod
    def get_all_items_filtered(self, attribute_filter: Optional[str] = None) -> Optional[Union[List[ItemsFiltered], List[str]]]:
        """
        Retrieves all relevant items (e.g., movies, shows) from the library and filters them.
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