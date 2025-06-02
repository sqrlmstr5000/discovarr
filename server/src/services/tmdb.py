import requests
import logging
import json
import sys
from typing import Optional

class TMDB:
    """
    A class to interact with the TMDB API for retrieving media information, such as poster art.
    """

    def __init__(self, tmdb_api_key: str):
        """
        Initializes the Tmdb class with the API key.

        Args:
            tmdb_api_key (str): The API key for TMDB.
        """
        # Setup Logging
        self.logger = logging.getLogger(__name__)

        self.tmdb_api_key = tmdb_api_key
        if not self.tmdb_api_key:
            self.logger.error("TMDB API key is not configured.")

    def get_media_detail(self, tmdb_id: str, media_type: str) -> Optional[str]:
        if not self.tmdb_api_key:
            self.logger.error("TMDB API key is not configured.")
            return None

        base_url = "https://api.themoviedb.org/3"
        endpoint = f"{base_url}/{media_type}/{tmdb_id}"
        params = {
            "language": "en-US",
        }
        headers = {
            "Authorization": f"Bearer {self.tmdb_api_key}",
        }

        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch {tmdb_id} from TMDB: {e}")
            return None
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from TMDB.")
            return None
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred while fetching {tmdb_id}: {e}")
            return None

    def lookup_media(self, query: str, media_type: str) -> Optional[dict]:
        """
        Searches for media (TV show or movie) using the TMDB search API.

        Args:
            query (str): The search query (title of movie or TV show)
            media_type (str): Type of media to search for ('tv' or 'movie')

        Returns:
            Optional[dict]: First search result containing media details or None if not found
                Returns fields like:
                - id: TMDB ID
                - title/name: Title of movie/show
                - overview: Plot description
                - first_air_date/release_date: Release date
                - poster_path: Poster image path
        """
        if not self.tmdb_api_key:
            self.logger.error("TMDB API key is not configured.")
            return None

        if media_type not in ['tv', 'movie']:
            self.logger.error(f"Invalid media type: {media_type}. Must be 'tv' or 'movie'")
            return None

        base_url = "https://api.themoviedb.org/3"
        endpoint = f"{base_url}/search/{media_type}"
        
        params = {
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.tmdb_api_key}",
        }

        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            if not results:
                self.logger.warning(f"No {media_type} found for query: {query}")
                return None

            # Return the first result
            return results[0]

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to search {media_type} on TMDB: {e}")
            return None
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from TMDB.")
            return None
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred while searching {media_type}: {e}")
            return None