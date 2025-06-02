import requests
import json
import logging
from typing import Optional, Dict, Any
from .response import APIResponse # Import the APIResponse class

class Api:
    def __init__(self, url: str, api_key: str, api_key_header_name: str = "X-Api-Key", api_base_path: str = "api/v3"):
        """Initialize a generic API client.

        Args:
            url (str): The base URL of the API server (e.g., "http://your-server:8080")
            api_key (str): The API key for authentication.
            api_key_header_name (str): The name of the HTTP header used to send the API key.
            api_base_path (str): The base path for all API endpoints (e.g., "api/v3").
                                 If empty, requests will be made directly against the base URL.
        """
        self.logger = logging.getLogger(__name__)
        self.url = url.rstrip('/') # Ensure no trailing slash for consistent URL building
        self.api_key = api_key
        self.api_key_header_name = api_key_header_name
        # Ensure api_base_path is clean and doesn't affect URL construction negatively if empty
        self.api_base_path = api_base_path.strip('/')
        self.headers = {
            self.api_key_header_name: api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> APIResponse:
        """Make a request to the configured API.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint (str): API endpoint path (e.g., "users", "items/1").
                            It will be appended to the base URL and API base path.
            params (Optional[Dict]): Query parameters for the request.
            data (Optional[Dict]): Data to send with request (will be JSON serialized for POST/PUT).

        Returns:
            APIResponse: An APIResponse object containing the result of the API call.
        """
        path_parts = [self.api_base_path, endpoint.lstrip('/')]
        actual_path = "/".join(p for p in path_parts if p) # Joins non-empty parts
        full_url = f"{self.url}/{actual_path}"

        self.logger.debug(f"Making {method} request to {full_url} with params={params}, data is_present={data is not None}")

        try:
            response = requests.request(method, full_url, headers=self.headers, params=params, json=data)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            if response.status_code == 204: # No Content
                return APIResponse(success=True, data=None, status_code=response.status_code)
            
            # Attempt to parse JSON, assuming most successful responses are JSON
            # If response is empty but status is 2xx (e.g. 200 with empty body), .json() might fail
            try:
                response_data = response.json()
            except json.JSONDecodeError as je:
                if not response.text: # Empty body with a 2xx status other than 204
                    self.logger.debug(f"Successful response {response.status_code} with empty body from {method} {full_url}.")
                    return APIResponse(success=True, data=None, status_code=response.status_code)
                # Non-empty, non-JSON successful response (should be rare for APIs this client targets)
                self.logger.warning(f"Could not decode JSON from successful response for {method} {full_url}: {je}. Body: {response.text[:100]}")
                return APIResponse(success=False, status_code=response.status_code, message="Failed to decode JSON from successful response.", error={"details": response.text})

            return APIResponse(success=True, data=response_data, status_code=response.status_code)

        except requests.exceptions.HTTPError as e:
            response_content = None # Could be dict, list from JSON, or str
            response_text_data = e.response.text if e.response is not None else "No response body"
            status_code_data = e.response.status_code if e.response is not None else None

            if e.response is not None:
                try:
                    response_content = e.response.json()
                    if isinstance(response_content, list):
                        errors = []
                        for error in response_content:
                            errors.append(f"{error.get("errorCode")}: {error.get("errorMessage")}")

                        if len(errors) > 0:
                            response_content = errors
                except json.JSONDecodeError:
                    self.logger.debug(f"Could not decode JSON from error response body: {response_text_data}")
            
            error_payload = response_content if response_content is not None else response_text_data
            
            err_msg = f"API HTTP Error for {method} {full_url}"
            self.logger.error(f"{err_msg}. Status: {status_code_data}. Body: {response_text_data[:500]}") # Log potentially large body truncated
            return APIResponse(
                success=False,
                status_code=status_code_data,
                message=err_msg,
                error={"details": error_payload}
            )
        except requests.exceptions.RequestException as e: # Covers DNS errors, connection timeouts, etc.
            err_msg = f"API Request Error for {method} {full_url}: {e}"
            self.logger.error(err_msg)
            return APIResponse(success=False, message=err_msg, error={"details": str(e)})
        except json.JSONDecodeError as e: # Should be caught by specific try-except for response.json() above.
                                          # This is a fallback for unexpected JSON errors during success.
            status_code_data = response.status_code if 'response' in locals() and hasattr(response, 'status_code') else None
            response_text_data = response.text if 'response' in locals() and hasattr(response, 'text') else str(e)
            err_msg = f"Failed to decode successful JSON response from API for {method} {full_url}: {e}"
            self.logger.error(f"{err_msg} Body: {response_text_data[:500]}")
            return APIResponse(
                success=False,
                status_code=status_code_data,
                message=err_msg,
                error={"details": response_text_data}
            )