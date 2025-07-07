import logging
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse
import os
import asyncio
import aiohttp
import aiofiles

class ImageCacheService:
    """
    A service to download and cache images locally.
    """

    def __init__(self, cache_base_dir: str = "/cache/image"):
        """
        Initializes the ImageCacheService.

        Args:
            cache_base_dir (str): The base directory where images will be cached.
        """
        self.logger = logging.getLogger(__name__)
        self.cache_base_dir = Path(cache_base_dir)
        self._ensure_cache_dir_exists()

    def _ensure_cache_dir_exists(self) -> None:
        """Ensures that the cache directory exists."""
        try:
            self.cache_base_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Cache directory ensured at: {self.cache_base_dir}")
            # Create 'tv' and 'movie' subdirectories
            (self.cache_base_dir / 'tv').mkdir(exist_ok=True)
            (self.cache_base_dir / 'movie').mkdir(exist_ok=True)
            self.logger.debug(f"Ensured 'tv' and 'movie' subdirectories under {self.cache_base_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create cache directory at {self.cache_base_dir}: {e}", exc_info=True)

    def _get_file_extension_from_url(self, image_url: str) -> Optional[str]:
        """
        Attempts to extract a file extension from the image URL.
        """
        try:
            path = urlparse(image_url).path
            ext = os.path.splitext(path)[1]
            return ext if ext else '.jpg' # Default to .jpg if no extension found
        except Exception:
            return '.jpg' # Default on any parsing error

    async def save_image_from_url(self, session: aiohttp.ClientSession, image_url: str, provider_name: str, item_id: str, media_type: str) -> Optional[str]:
        """
        Downloads an image from a URL and saves it to the local cache.

        Args:
            image_url (str): The URL of the image to download.
            provider_name (str): The name of the provider (e.g., 'plex', 'tmdb').
            item_id (str): The unique ID of the item associated with the image.
            session (aiohttp.ClientSession): An active aiohttp client session.

        Returns:
            Optional[str]: The local path to the cached image if successful, otherwise None.
                           The path will be relative to the server root, e.g., "/cache/plex_123.jpg".
        """
        if not image_url:
            self.logger.warning("No image URL provided. Skipping cache.")
            return None

        try:
            extension = self._get_file_extension_from_url(image_url)
            # Sanitize item_id to be safe for filenames (e.g., replace slashes if any)
            safe_item_id = str(item_id).replace('/', '_').replace('\\', '_')
            filename = f"{safe_item_id}{extension}"
            # Construct the path using Path objects for proper concatenation
            local_image_path = self.cache_base_dir / Path(media_type) / filename
            #web_accessible_path = f"/{self.cache_base_dir.name}/{filename}"

            if local_image_path.exists():
                self.logger.info(f"Image already cached at {local_image_path}. Using existing file.")
                return str(Path(media_type) / filename)

            # Ensure the target directory exists before writing
            local_image_path.parent.mkdir(parents=True, exist_ok=True)

            async with session.get(image_url, timeout=10) as response:
                response.raise_for_status()  # Will raise an ClientResponseError for bad responses (4XX or 5XX)

                async with aiofiles.open(local_image_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        
            self.logger.info(f"Successfully cached image to {local_image_path}")
            return str(Path(media_type) / filename)
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to download image from {image_url}: {e}")
        except IOError as e:
            self.logger.error(f"Failed to save image to {local_image_path}: {e}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while caching image from {image_url}: {e}", exc_info=True)
        return None

    def delete_cached_image(self, relative_path: str) -> bool:
        """
        Deletes a specific image file from the cache.

        Args:
            relative_path (str): The relative path of the file to delete (e.g., "plex/movie/123.jpg").

        Returns:
            bool: True if the file was deleted successfully or did not exist, False on error.
        """
        if not relative_path:
            self.logger.warning("No relative_path provided for deletion. Skipping.")
            return True # Consider it success if no action needed
        
        local_image_path = self.cache_base_dir / relative_path
        if local_image_path.exists():
            try:
                local_image_path.unlink()
                self.logger.info(f"Successfully deleted cached image: {local_image_path}")
                return True
            except OSError as e:
                self.logger.error(f"Failed to delete cached image {local_image_path}: {e}")
                return False
        else:
            self.logger.info(f"Cached image {local_image_path} not found. No deletion needed.")
            return True