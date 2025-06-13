import logging
import json
from typing import Optional, Dict, Any, List

import aiohttp

from base.llm_provider_base import LLMProviderBase
from services.models import SettingType # For default settings

class LangflowProvider(LLMProviderBase):
    """
    LLMProvider implementation for interacting with a Langflow API.
    """
    PROVIDER_NAME = "langflow"

    def __init__(self, base_url: str, flow_id: str, api_key: Optional[str] = None,
                 input_field: str = "input_value", output_field: str = "result",
                 default_tweaks_str: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.flow_id = flow_id # Default flow_id for this instance
        self.input_field = input_field
        self.output_field = output_field
        
        self.default_tweaks: Dict[str, Any] = {}
        if default_tweaks_str:
            try:
                self.default_tweaks = json.loads(default_tweaks_str)
                if not isinstance(self.default_tweaks, dict):
                    self.logger.warning(f"Parsed default_tweaks is not a dictionary: {self.default_tweaks}. Using empty tweaks.")
                    self.default_tweaks = {}
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse default_tweaks JSON string: {default_tweaks_str}. Using empty tweaks.")
                self.default_tweaks = {}

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}" # Common, adjust if needed

    @property
    def name(self) -> str:
        return LangflowProvider.PROVIDER_NAME

    async def get_similar_media(
        self,
        model: str, # For Langflow, this 'model' parameter is the flow_id to run
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        if not model: # model is expected to be the flow_id for this specific call
            self.logger.error("Flow ID (as 'model' parameter) is required for Langflow run.")
            return {'success': False, 'message': "Flow ID (as 'model' parameter) is required for Langflow run.", 'status_code': 400}

        endpoint = f"{self.base_url}/api/v1/run/{model}?stream=false"

        current_tweaks = self.default_tweaks.copy()
        # Example of how system_prompt and temperature could be passed via tweaks
        # This assumes the Langflow flow is designed to accept these tweak names.
        if system_prompt and "system_message" in current_tweaks: # Or whatever the tweak key is
             current_tweaks["system_message"] = system_prompt
        if temperature is not None and "temperature" in current_tweaks: # Or whatever the tweak key is
             current_tweaks["temperature"] = temperature

        input_payload_component: Dict[str, Any]
        if self.input_field == "input_value":
            input_payload_component = {"input_value": prompt}
        else:
            input_payload_component = {"inputs": {self.input_field: prompt}}

        payload = {
            **input_payload_component,
            "output_type": "chat", # Adjust if your flow's output is different (e.g., "data")
            "input_type": "chat",  # Adjust if your flow's input type is different
            "tweaks": current_tweaks,
            "stream": False
        }

        self.logger.debug(f"Requesting Langflow: POST {endpoint} with payload: {json.dumps(payload)}")

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(endpoint, json=payload) as response:
                    response_text = await response.text()
                    if response.status != 200:
                        self.logger.error(f"Langflow API error ({response.status}): {response_text}")
                        return {'success': False, 'message': f"Langflow API error: {response_text}", 'status_code': response.status}

                    try:
                        langflow_response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to decode JSON from Langflow response: {response_text}")
                        return {'success': False, 'message': "Failed to decode JSON from Langflow.", 'status_code': 500}

                    final_output_content = None
                    if "outputs" in langflow_response_data and langflow_response_data["outputs"]:
                        first_main_output = langflow_response_data["outputs"][0]
                        if "outputs" in first_main_output and first_main_output["outputs"]:
                            component_outputs_list = first_main_output["outputs"]
                            if component_outputs_list:
                                actual_results_dict = component_outputs_list[0].get("outputs", {})
                                final_output_content = actual_results_dict.get(self.output_field)

                    if final_output_content is None:
                        self.logger.error(f"Could not find output field '{self.output_field}' in Langflow response. Response: {json.dumps(langflow_response_data, indent=2)}")
                        return {'success': False, 'message': f"Output field '{self.output_field}' not found in Langflow response.", 'status_code': 500}

                    try:
                        if isinstance(final_output_content, str):
                            parsed_suggestions = json.loads(final_output_content)
                        elif isinstance(final_output_content, dict):
                            parsed_suggestions = final_output_content
                        else:
                            raise ValueError(f"Output field content is not a parsable string or dictionary, got {type(final_output_content)}.")

                        if not isinstance(parsed_suggestions, dict) or "suggestions" not in parsed_suggestions:
                             self.logger.error(f"Parsed suggestions from Langflow's output field '{self.output_field}' is not in the expected format (missing 'suggestions' key). Content: {parsed_suggestions}")
                             return {'success': False, 'message': f"Langflow output format error in field '{self.output_field}'.", 'status_code': 500}

                        return {
                            'response': parsed_suggestions,
                            'token_counts': {} # Langflow /run endpoint doesn't provide token counts
                        }
                    except (json.JSONDecodeError, ValueError) as e:
                        self.logger.error(f"Failed to parse or validate content from Langflow's output field '{self.output_field}': {e}. Content: {final_output_content}")
                        return {'success': False, 'message': f"Error processing Langflow's output field '{self.output_field}': {e}", 'status_code': 500}

        except aiohttp.ClientError as e:
            self.logger.error(f"AIOHTTP client error connecting to Langflow: {e}")
            return {'success': False, 'message': f"Error connecting to Langflow: {e}", 'status_code': 503}
        except Exception as e:
            self.logger.error(f"Unexpected error in Langflow get_similar_media: {e}", exc_info=True)
            return {'success': False, 'message': f"Unexpected error: {e}", 'status_code': 500}

    async def get_models(self) -> Optional[List[str]]:
        """Lists available flow IDs from the Langflow API."""
        if not self.base_url:
            self.logger.warning("Langflow base URL is not configured. Cannot list flows.")
            return None

        endpoint = f"{self.base_url}/api/v1/flows/"
        self.logger.debug(f"Requesting Langflow flows: GET {endpoint}")

        try: # Outer try for ClientSession and network errors
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(endpoint) as response:
                    response_text = await response.text()
                    if response.status != 200:
                        self.logger.error(f"Langflow API error listing flows ({response.status}): {response_text}")
                        # Return None or an empty list depending on desired behavior on error
                        return None

                    try:
                        flows_data = json.loads(response_text)
                        if not isinstance(flows_data, list):
                             self.logger.error(f"Langflow API returned unexpected format for flows: {flows_data}")
                             return None
                        #
                        # TODO: Use "name" attribute to show in the dropdown, use id for the value 
                        #       Need to refactor the get_model for each llm provider to support this.
                        #

                        # Extract flow IDs
                        flow_ids = [flow.get("id") for flow in flows_data if flow.get("id")]
                        return flow_ids
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to decode JSON from Langflow flows response: {response_text}")
                        return None
        except aiohttp.ClientError as e:
            self.logger.error(f"AIOHTTP client error listing Langflow flows: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error listing Langflow flows: {e}", exc_info=True)
            return None
        # return [] # This was originally here, but None is more consistent for errors. If no flows, an empty list is returned from the try block.

    @classmethod
    def get_default_settings(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "enabled": {"value": False, "type": SettingType.BOOLEAN, "description": "Enable Langflow provider."},
            "base_url": {"value": "http://langflow:7860", "type": SettingType.URL, "description": "Base URL of the Langflow server (e.g., http://localhost:7860).", "required": True},
            "api_key": {"value": None, "type": SettingType.STRING, "description": "API Key for Langflow (if authentication is enabled).", "required": True},
            "flow_id": {"value": None, "type": SettingType.STRING, "description": "The ID of the default Langflow flow to use for suggestions.", "required": True},
            "input_field": {"value": "input_value", "type": SettingType.STRING, "description": "Name of the input field for the prompt. If 'input_value', prompt is sent as root key. Otherwise, sent as {\"inputs\": {\"<input_field>\": prompt}}.", "required": False},
            "output_field": {"value": "result", "type": SettingType.STRING, "description": "Name of the field in Langflow's output containing the JSON string of suggestions (e.g., {\"suggestions\": [...]}).", "required": True},
            "default_tweaks": {"value": "{}", "type": SettingType.STRING, "description": "JSON string representing default tweaks to pass to the Langflow flow (e.g., {\"llm_model_name\": \"gpt-4\"}).", "required": False},
            "base_provider": {"value": "llm", "type": SettingType.STRING, "show": False, "description": "Base Provider Type"},
        }