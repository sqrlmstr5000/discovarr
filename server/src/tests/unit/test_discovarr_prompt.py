import pytest
from unittest.mock import MagicMock, patch
from discovarr import Discovarr # Keep this for type hinting if needed
from services.models import LibraryUser, ItemsFiltered

from tests.unit.base.base_discovarr_tests import mocked_discovarr_instance # Import the new base fixture


def test_get_prompt_basic_scenario(mocked_discovarr_instance: Discovarr):
    dv = mocked_discovarr_instance
    
    # --- Configure mocks for this specific test ---
    # Mock the LLMService's get_prompt method directly
    mock_rendered_prompt = "Mocked prompt string for basic scenario"
    dv.llm_service.get_prompt.return_value = mock_rendered_prompt
    
    # Mock settings to provide a default prompt template
    default_prompt_template = 'Default template'
    dv.settings.get.side_effect = lambda group, key, default=None: \
        default_prompt_template if group == "app" and key == "default_prompt" else default
    
    # --- Call the method under test ---
    prompt = dv.get_prompt(limit=5, media_name="Test Movie")

    # --- Assertions ---
    # Assert that Discovarr.get_prompt returned the value from the mocked LLMService.get_prompt
    assert prompt == mock_rendered_prompt
    
    # Verify mock calls
    # Assert that Discovarr.get_prompt called LLMService.get_prompt with the correct arguments
    dv.llm_service.get_prompt.assert_called_once_with(
        limit=5,
        media_name="Test Movie",
        template_string=None # Discovarr.get_prompt passes None if not specified
    )


def test_get_prompt_with_default_plex_user(mocked_discovarr_instance: Discovarr):
    dv = mocked_discovarr_instance # dv is already the mocked instance
    
    default_prompt_template = "Favs: {{ favorites }}"
    test_specific_settings = {
        # The default_user setting is used *inside* LLMService.get_prompt,
        # so we don't need to mock get_user_by_name here.
        # We just need to ensure the default_prompt is available via settings.
        ("app", "default_prompt"): default_prompt_template,
    }
    dv.settings.get.side_effect = lambda group, key, default=None: test_specific_settings.get((group, key), default)

    # Mock the LLMService's get_prompt method
    mock_rendered_prompt = "Mocked prompt string with default user logic handled internally"
    dv.llm_service.get_prompt.return_value = mock_rendered_prompt

    prompt = dv.get_prompt(limit=3, media_name="Another Movie")

    assert prompt == mock_rendered_prompt
    dv.llm_service.get_prompt.assert_called_once_with(
        limit=3, media_name="Another Movie", template_string=None # Discovarr.get_prompt passes None
    )


def test_get_prompt_custom_template_string(mocked_discovarr_instance: Discovarr):
    dv = mocked_discovarr_instance # dv is already the mocked instance
    
    # Ensure providers are disabled via settings mock so they don't interfere
    dv.settings.get.side_effect = lambda group, key, default=None: {
        # Only need to mock the default prompt setting if the test might fall back to it
        ("app", "default_prompt"): "Should not be used",
    }.get((group, key), default)

    # Mock the LLMService's get_prompt method
    mock_rendered_prompt = "Mocked prompt string from custom template"
    dv.llm_service.get_prompt.return_value = mock_rendered_prompt

    custom_template = "Custom: {{ media_name }} | Exclude: {{ all_media }} | Favs: {{ favorites }} | History: {{ watch_history }}"
    prompt = dv.get_prompt(limit=10, media_name="Custom Media", template_string=custom_template)

    assert prompt == mock_rendered_prompt
    dv.llm_service.get_prompt.assert_called_once_with(
        limit=10, media_name="Custom Media", template_string=custom_template
    )
