import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from enum import Enum
from urllib.parse import urlparse
from services.models import Settings

if TYPE_CHECKING:
    from ..aiarr import AiArr # For type hinting AiArr instance

class SettingType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER" 
    BOOLEAN = "BOOLEAN"
    URL = "URL"
    FLOAT = "FLOAT"

class SettingsService:
    """
    Service for managing application settings.
    Handles loading, saving, and providing default values for settings.
    Stores settings in the database with proper type validation.
    """
    
    # Default settings by group with types and validation
    DEFAULT_PROMPT = "Recommend {{limit}} tv series or movies similar to {{media_name}}. \n\nExclude the following media from your recommendations: {{media_exclude}}"
    DEFAULT_SETTINGS = {
        "app": {
            "default_prompt": {"value": DEFAULT_PROMPT, "type": SettingType.STRING, "description": "Default prompt template to use on the Search page"},
            "recent_limit": {"value": 10, "type": SettingType.INTEGER, "description": "Number of recent items to fetch"},
            "test_mode": {"value": False, "type": SettingType.BOOLEAN, "description": "Sets the search_for_missing when requesting media from Radarr and Sonarr to False. This won't download anything just add the media."},
            "backup_before_upgrade": {"value": True, "type": SettingType.BOOLEAN, "description": "Automatically backup the database before running migrations/upgrades."},
            "auto_media_save": {"value": True, "type": SettingType.BOOLEAN, "description": "Automatically save the results from a Search to the AiArr Media table"},
            "system_prompt": {"value": "You are a movie recommendation assistant. Your job is to suggest movies to users based on their preferences and current context.", "type": SettingType.STRING, "description": "Default system prompt to guide the model's behavior."},
        },
        "jellyfin": {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Jellyfin integration."},
            "url": {"value": "http://jellyfin:8096", "type": SettingType.URL, "description": "Jellyfin server URL"},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Jellyfin API key"},
        },
        "plex": {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Plex integration."},
            "url": {"value": "http://plex:32400", "type": SettingType.URL, "description": "Plex server URL"},
            "api_token": {"value": None, "type": SettingType.STRING, "description": "Plex X-Plex-Token"},
        },
        "radarr": {
            "url": {"value": "http://radarr:7878", "type": SettingType.URL, "description": "Radarr server URL"},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Radarr API key"},
            "default_quality_profile_id": {"value": None, "type": SettingType.INTEGER, "description": "Radarr Default quality profile ID"},
        },
        "sonarr": {
            "url": {"value": "http://sonarr:8989", "type": SettingType.URL, "description": "Sonarr server URL"},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Sonarr API key"},
            "default_quality_profile_id": {"value": None, "type": SettingType.INTEGER, "description": "Radarr Default quality profile ID"},
        },
        "gemini": {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Gemini integration."},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "Gemini API key"},
            "model": {"value": None, "type": SettingType.STRING, "description": "Gemini model name"},
            "limit": {"value": 10, "type": SettingType.INTEGER, "description": "Maximum number of suggestions to return"},
            "thinking_budget": {"value": 1024, "type": SettingType.FLOAT, "description": "Gemini thinking budget controls the computational budget the model uses for internal thought processes. Setting it to 0 can disable explicit thinking steps, potentially leading to faster but less 'reasoned' responses for complex tasks. If you set a value under 1024 tokens, the API will actually reset it to 1024 tokens if thinking is still enabled. So, effectively, the lowest non-zero thinking budget is 1024 tokens. The maximum thinking_budget you can set is 24,576 tokens."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "Gemini temperature for controlling randomness (e.g., 0.7). Higher values mean more random. Values typically range from 0.0 to 2.0"},
        },
        "ollama": {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable or disable Ollama integration."},
            "base_url": {"value": "http://localhost:11434", "type": SettingType.URL, "description": "Ollama server base URL (e.g., http://localhost:11434)."},
            "model": {"value": None, "type": SettingType.STRING, "description": "Ollama model name to use (e.g., llama3, mistral)."},
            "temperature": {"value": 0.7, "type": SettingType.FLOAT, "description": "Ollama temperature for controlling randomness (e.g., 0.7). Higher values mean more random."},
        },
        "tmdb": {
            "api_key": {"value": None, "type": SettingType.STRING, "description": "TMDB API key"},
        },
        
    }

    def __init__(self, aiarr_app: Optional['AiArr'] = None):
        """Initialize the settings service."""
        self.logger = logging.getLogger(__name__)
        self.aiarr_app = aiarr_app
        self._initialize_settings()

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

    def _initialize_settings(self) -> None:
        """
        Create settings in database if they don't exist.
        For each setting, checks environment variable {GROUP}_{NAME} in uppercase.
        Falls back to value from DEFAULT_SETTINGS if env var not set.
        """
        import os

        for group, settings in self.DEFAULT_SETTINGS.items():
            for name, config in settings.items():
                # Check environment variable first (e.g. JELLYFIN_URL for jellyfin.url)
                env_var = f"{group.upper()}_{name.upper()}"
                env_value = os.environ.get(env_var)
                
                if env_value is not None:
                    self.logger.info(f"Using environment variable {env_var}")

                try:
                    Settings.get(Settings.group == group, Settings.name == name)
                except Settings.DoesNotExist:
                    self.logger.info(f"Creating setting {group}.{name} in database")
                    Settings.create(
                        group=group,
                        name=name,
                        value=env_value,  # Use environment variable value if set
                        type=config["type"].value,
                        description=config["description"],
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    self.logger.info(f"Created setting {group}.{name} with value from {env_var if env_value else 'defaults'}")

    def get(self, group: str, name: str) -> Optional[Any]:
        """Get a setting value with proper type conversion."""
        try:
            # First check if the setting exists in our defaults
            if group not in self.DEFAULT_SETTINGS or name not in self.DEFAULT_SETTINGS[group]:
                self.logger.warning(f"No default configuration for setting {group}.{name}")
                return None

            setting_config = self.DEFAULT_SETTINGS[group][name]
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
            if self.aiarr_app: # aiarr_app is an instance of AiArr
                try:
                    self.logger.info(f"Attempting to reload AiArr configuration after updating {group}.{name}.")
                    self.aiarr_app.reload_configuration()
                    self.logger.info(f"AiArr configuration reloaded successfully after updating {group}.{name}.")
                except ValueError as e: # Catch validation errors from AiArr._validate_configuration
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
        for group, group_settings in self.DEFAULT_SETTINGS.items():
            if group not in result:
                result[group] = {}
            for name, config in group_settings.items():
                actual_value = config["value"] # Default value
                description = config["description"]
                setting_type = config["type"]
                
                setting = settings.get((group, name))
                if setting and setting.value is not None:
                    actual_value = self._convert_value(setting.value, setting_type)
                
                result[group][name] = {
                    "value": actual_value,
                    "description": description
                }
        return result

    def get_settings_by_group(self, group: str) -> Dict[str, Any]:
        """Get all settings in a group."""
        if group not in self.DEFAULT_SETTINGS:
            return {}
            
        result = {}
        for name in self.DEFAULT_SETTINGS[group]:
            result[name] = self.get(group, name)
        return result
