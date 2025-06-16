import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

class ResearcharrService:
    """
    A service to handle text assimilation tasks, primarily creating embeddings.
    """

    def __init__(self, model_name: str = 'multi-qa-mpnet-base-cos-v1'):
        """
        Initializes the AssimilateService.

        Args:
            model_name (str): The name of the SentenceTransformer model to use.
        """
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        try:
            self.model = SentenceTransformer(self.model_name)
            self.logger.info(f"Successfully loaded SentenceTransformer model: {self.model_name}")
        except Exception as e:
            self.logger.error(f"Failed to load SentenceTransformer model '{self.model_name}': {e}", exc_info=True)
            self.model = None

    def create_embedding(self, text: str) -> Optional[List[float]]:
        """
        Creates an embedding for the given text using the pre-loaded SentenceTransformer model.
        """
        if not self.model:
            self.logger.error("SentenceTransformer model is not loaded. Cannot create embedding.")
            return None
        try:
            embedding = self.model.encode(text.strip())
            return embedding.tolist() # Convert numpy array to list of floats
        except Exception as e:
            self.logger.error(f"Error creating embedding for text: {e}", exc_info=True)
            return None