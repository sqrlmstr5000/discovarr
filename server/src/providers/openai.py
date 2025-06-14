import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from providers.openai import OpenAI

class Suggestion(BaseModel):
    title: str
    description: str
    similarity: str
    mediaType: str
    imdb_id: str
    imdb_url: str
    imdb_score: int
    tmdb_url: str
    tmdb_id: str
    tvdb_id: str
    rt_url: str
    rt_score: int
    poster_url: str

class OpenAi:
    """
    A class to interact with the OpenAI API for finding similar media.
    """

    def __init__(self, openai_model: str, openai_api_key: str):
        """
        Initializes the OpenAI class with API configurations.

        Args:
            openai_model (str): The OpenAI model to use (e.g., "gpt-4-turbo-preview")
            openai_api_key (str): The OpenAI API key
        """
        # Setup Logging
        self.logger = logging.getLogger(__name__)

        self.openai_model = openai_model
        self.openai_api_key = openai_api_key
        self.logger.info("Initializing OpenAI class...")
        self.logger.debug("OPENAI_MODEL: %s", self.openai_model)
        self.logger.debug("OPENAI_API_KEY: %s", self.openai_api_key)

        self.client = OpenAI(api_key=self.openai_api_key)

    def get_similar_media(self, media_name: str, all_media: str) -> Optional[Dict[str, Any]]:
        """
        Uses the OpenAI API to find media similar to the given media name.

        Args:
            media_name (str): The name of the movie or TV show
            all_media (str): List of media to exclude from recommendations

        Returns:
            dict: A dictionary containing the response from the OpenAI API, or None on error
        """
        if not self.openai_model:
            self.logger.error("OpenAI Model is not configured.")
            return None

        if not self.openai_api_key:
            self.logger.error("OpenAI API Key is not configured.")
            return None

        try:
            system_prompt = """You are a movie and TV show recommendation expert. 
            Respond with exactly 5 recommendations in a JSON list with the following format. Each recommendation should include:
            {
                "title": "Title of the media",
                "description": "Description of the media",
                "similarity": "Why did you choose this media?",
                "mediaType": "movie or tv",
                "imdb_id": "IMDB ID",
                "imdb_url": "URL of the media from imdb.com",
                "imdb_score": "IMDB score (numeric)",
                "tmdb_url": "URL to the media from themoviedb.org",
                "tmdb_id": "themoviedb.org ID",
                "tvdb_id": "TheTVDB.com Movie ID",
                "rt_url": "Rotten Tomatoes URL of the media",
                "rt_score": "Rotten Tomatoes Score (numeric)",
                "poster_url": ""
            }
            Verify all URLs and IDs match with the Title of the media before responding."""

            user_prompt = f"""Give me 5 tv series or movies similar to {media_name}. 
            Exclude the following media from your recommendations: 
            {all_media}

            Double check to ensure the imdb_url page title contains the title of the media. 
            Correct the imdb_id if necessary.
            The tmdb_url page title should also contain the title of the media. 
            Correct the tmdb_id if necessary."""

            json_schema = Suggestion.model_json_schema()
            response = self.client.beta.chat.completions.parse(
                model=self.openai_model,
                response_format=Suggestion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract the JSON content from the response
            content = response.choices[0].message.content
            openai_response = json.loads(content)
            
            return openai_response
        except json.JSONDecodeError:
            error_message = "OpenAI API returned non-JSON response."
            self.logger.error(error_message)
            self.logger.debug(response)
            return None
        except Exception as e:
            error_message = f"OpenAI API error: {e}"
            self.logger.exception(error_message)
            return None
