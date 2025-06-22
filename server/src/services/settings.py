import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from urllib.parse import urlparse
from .models import Settings, SettingType, DEFAULT_PROMPT_TEMPLATE, DEFAULT_PROMPT_RESEARCH_TEMPLATE

if TYPE_CHECKING:
    from ..discovarr import Discovarr # For type hinting Discovarr instance

class SettingsService:
    """
    Service for managing application settings.
    Handles loading, saving, and providing default values for settings.
    Stores settings in the database with proper type validation.
    """
    
    # Default settings by group with types and validation
    
    _BASE_DEFAULT_SETTINGS = {
        "app": {
            "default_prompt": {"value": DEFAULT_PROMPT_TEMPLATE, "type": SettingType.STRING, "description": "Default prompt template to use on the Search page"},
            "default_research_prompt": {"value": DEFAULT_PROMPT_RESEARCH_TEMPLATE, "type": SettingType.STRING, "description": "Default prompt template to use on the Research page"},
            "recent_limit": {"value": 10, "type": SettingType.INTEGER, "description": "Number of recent items to fetch"},
            "suggestion_limit": {"value": 20, "type": SettingType.INTEGER, "description": "Maximum number of suggestions to return"},
            "request_only": {"value": False, "type": SettingType.BOOLEAN, "description": "Sets the search_for_missing to False when requesting media from Radarr and Sonarr. This won't start a search just add the media."},
            "auto_media_save": {"value": True, "type": SettingType.BOOLEAN, "description": "Automatically save the results from a Search to the Discovarr Media table"},
            "system_prompt": {"value": "You are a movie recommendation assistant. Your job is to suggest movies to users based on their preferences and current context.", "type": SettingType.STRING, "description": "Default system prompt to guide the model's behavior."},
        },
        "tmdb": {
            "api_key": {"value": None, "type": SettingType.STRING, "description": "TMDB API Read Access Token", "required": True},
        },
    }
    # DEFAULT_SETTINGS will be populated by _build_default_settings_if_needed
    # This ensures LLM provider defaults are loaded dynamically.
    DEFAULT_SETTINGS: Dict[str, Dict[str, Any]] = {}

    def __init__(self, discovarr_app: Optional['Discovarr'] = None):
        """Initialize the settings service."""
        self.logger = logging.getLogger(__name__)
        self.discovarr_app = discovarr_app
        SettingsService._build_default_settings_if_needed()
        # self._initialize_settings() # Moved to be called by Discovarr after DB init

    def _validate_value(self, value: Any, setting_type: SettingType) -> bool:
        """Validate a value matches its expected type."""
        if value is None:
            return True

        try:
            if setting_type == SettingType.INTEGER:
                int(str(value))
            elif setting_type == SettingType.BOOLEAN:
                str(value).lower() in ('true', 'false', '1', '0', 't', 'f', 'y', 'n', 'yes', 'no')
            elif setting_type == SettingType.URL:
                result = urlparse(str(value))
                return all([result.scheme, result.netloc])
            elif setting_type == SettingType.FLOAT:
                float(str(value))
            return True
        except (ValueError, AttributeError):
            return False

    def _convert_value(self, value: Optional[str], setting_type: SettingType) -> Any:
        """Convert string value from database to appropriate type."""
        if value is None:
            return None
            
        if setting_type == SettingType.INTEGER:
            return int(value)
        elif setting_type == SettingType.BOOLEAN:
            return value.lower() in ('true', '1', 't', 'y', 'yes')
        elif setting_type == SettingType.URL:
            # Validate URL format
            result = urlparse(value)
            if all([result.scheme, result.netloc]):
                return value
            return None
        elif setting_type == SettingType.FLOAT:
            return float(value)
        return value

    @staticmethod
    def _build_default_settings_if_needed():
        """
        Builds the complete DEFAULT_SETTINGS dictionary by combining base settings
        with settings from LLM providers. This method is idempotent.
        """
        if SettingsService.DEFAULT_SETTINGS:  # Already built
            return

        # Delayed imports to prevent circular dependencies at module load time
        from providers.gemini import GeminiProvider
        from providers.openai import OpenAIProvider
        from providers.ollama import OllamaProvider
        from providers.plex import PlexProvider
        from providers.jellyfin import JellyfinProvider
        from providers.trakt import TraktProvider
        from providers.radarr import RadarrProvider # Import Radarr
        from providers.sonarr import SonarrProvider # Import Sonarr
        from providers.jellyseerr import JellyseerrProvider # Import JellyseerrProvider
        from providers.overseerr import OverseerrProvider
        # Add other ProviderBase implementations here

        # Define lists of provider classes
        # Ensure these classes have PROVIDER_NAME and get_default_settings
        provider_classes_to_load = [
            RadarrProvider,
            SonarrProvider,
            GeminiProvider,
            OpenAIProvider,
            OllamaProvider,
            PlexProvider,
            JellyfinProvider,
            TraktProvider,
            JellyseerrProvider,
            OverseerrProvider,
        ]

        current_default_settings = SettingsService._BASE_DEFAULT_SETTINGS.copy()
        
        for provider_class in provider_classes_to_load:
            if not hasattr(provider_class, 'PROVIDER_NAME') or not hasattr(provider_class, 'get_default_settings'):
                logging.getLogger(__name__).error(
                    f"Provider class {provider_class.__name__} is missing PROVIDER_NAME or get_default_settings static method."
                )
                continue
            
            provider_name = provider_class.PROVIDER_NAME
            provider_defaults = provider_class.get_default_settings()
            if provider_name in current_default_settings:
                logging.getLogger(__name__).warning(f"Provider '{provider_name}' defaults key already exists. Overwriting with specifics from {provider_class.__name__}.")
            current_default_settings[provider_name] = provider_defaults
            logging.getLogger(__name__).info(f"Loaded default settings for provider: {provider_name}")
        
        SettingsService.DEFAULT_SETTINGS = current_default_settings
        
    def _initialize_settings(self) -> None:
        """
        Initializes settings in the database.
        - Creates settings if they don't exist.
        - Overwrites existing settings with values from environment variables if they are set.
        """
        import os

        for group, settings in SettingsService.DEFAULT_SETTINGS.items():
            for name, config in settings.items():
                # Check environment variable (e.g., JELLYFIN_URL for jellyfin.url)
                env_var = f"{group.upper()}_{name.upper()}"
                env_value = os.environ.get(env_var)

                # Determine the value to use for creation
                value_for_creation = env_value if env_value is not None else config["value"]

                setting, created = Settings.get_or_create(
                    group=group,
                    name=name,
                    defaults={
                        'value': value_for_creation,
                        'type': config["type"].value,
                        'description': config["description"],
                    }
                )

                if created:
                    self.logger.info(f"Created setting {group}.{name} with value from {'environment variable ' + env_var if env_value is not None else 'defaults'}")
                elif env_value is not None and setting.value != env_value:
                    # Setting existed, but env var has a different value. Overwrite.
                    self.logger.info(f"Overwriting setting {group}.{name} with value from environment variable {env_var}")
                    setting.value = env_value
                    setting.updated_at = datetime.now()
                    setting.save()

    def get(self, group: str, name: str) -> Optional[Any]:
        """Get a setting value with proper type conversion."""
        try:
            # First check if the setting exists in our defaults
            if group not in SettingsService.DEFAULT_SETTINGS or name not in SettingsService.DEFAULT_SETTINGS[group]:
                self.logger.warning(f"No default configuration for setting {group}.{name}")
                return None

            setting_config = SettingsService.DEFAULT_SETTINGS[group][name]
            setting_type = setting_config["type"]

            # Try to get value from database
            try:
                setting = Settings.get(Settings.group == group, Settings.name == name)
                if setting.value is not None:
                    return self._convert_value(setting.value, setting_type)
            except Settings.DoesNotExist:
                self.logger.warning(f"Setting {group}.{name} not found in database")

            # Fall back to default from DEFAULT_SETTINGS
            return setting_config["value"]

        except Exception as e:
            self.logger.error(f"Error getting setting {group}.{name}: {e}")
            return None

    def set(self, group: str, name: str, value: Any) -> bool:
        """Set a setting value with type validation."""
        try:
            setting = Settings.get(Settings.group == group, Settings.name == name)
            old_db_value_str = setting.value # Store the current string value from DB
            setting_type = SettingType(setting.type)
            
            # Validate value type
            if not self._validate_value(value, setting_type):
                self.logger.error(f"Invalid value type for setting {group}.{name}")
                return False

            # Convert to string for storage
            setting.value = str(value) if value is not None else None
            setting.updated_at = datetime.now()
            setting.save()
            
            self.logger.info(f"Updated setting {group}.{name} to {value}")
            
            # Attempt to reload configuration with the new setting
            if self.discovarr_app: # discovarr_app is an instance of Discovarr
                try:
                    self.logger.info(f"Attempting to reload Discovarr configuration after updating {group}.{name}.")
                    self.discovarr_app.reload_configuration()
                    self.logger.info(f"Discovarr configuration reloaded successfully after updating {group}.{name}.")
                except ValueError as e: # Catch validation errors from Discovarr._validate_configuration
                    self.logger.error(f"Configuration reload failed after updating {group}.{name} to '{value}': {e}. Reverting setting.")
                    # Revert the setting in the database
                    setting.value = old_db_value_str
                    setting.updated_at = datetime.now() # Update timestamp for the revert action
                    setting.save()
                    self.logger.info(f"Reverted setting {group}.{name} to its previous value: '{old_db_value_str}'.")
                    return False # Indicate failure to the caller
            return True
        except Settings.DoesNotExist:
            self.logger.error(f"Setting {group}.{name} not found")
            return False
        except Exception as e:
            self.logger.error(f"Error updating setting {group}.{name}: {e}", exc_info=True)
            return False

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings grouped by their groups with proper type conversion."""
        result = {}
        
        # First get all settings from database for efficiency
        settings = {
            (s.group, s.name): s for s in Settings.select()
        }
        
        # Build result using DEFAULT_SETTINGS as template
        # Iterate over sorted group names for alphabetical order
        for group in sorted(SettingsService.DEFAULT_SETTINGS.keys()):
            group_settings = SettingsService.DEFAULT_SETTINGS[group]
            if group not in result:
                result[group] = {}
            for name, config in group_settings.items():
                # Only include settings where 'hide' not defined
                if config.get('hide'):
                    continue

                actual_value = config["value"] # Default value
                description = config["description"]
                setting_type = config["type"]
                show = config.get("show", True)
                required = config.get("required", False) # Get the required flag
                
                setting = settings.get((group, name))
                if setting and setting.value is not None:
                    actual_value = self._convert_value(setting.value, setting_type)
                
                result[group][name] = {
                    "value": actual_value,
                    "description": description,
                    "show": show,
                    "required": required, # Pass it to the frontend
                    "type": setting_type.value
                }
        return result

    def get_settings_by_group(self, group: str) -> Dict[str, Any]:
        """Get all settings in a group."""
        if group not in SettingsService.DEFAULT_SETTINGS:
            return {}
            
        result = {}
        for name in SettingsService.DEFAULT_SETTINGS[group]:
            result[name] = self.get(group, name)
        return result
