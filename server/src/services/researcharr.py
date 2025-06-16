import logging
from typing import List, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
from jinja2 import Template
from datetime import datetime

from .settings import SettingsService
from .llm import LLMService
from .models import MediaResearch # Import MediaResearch model

class ResearcharrService:
    """
    A service to handle text assimilation tasks, primarily creating embeddings.
    """

    def __init__(self,
                 settings_service: SettingsService,
                 llm_service: LLMService,
                 model_name: str = 'multi-qa-mpnet-base-cos-v1'):
        """
        Initializes the AssimilateService.

        Args:
            settings_service (SettingsService): Instance of the settings service.
            llm_service (LLMService): Instance of the LLM service.
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
        self.settings_service = settings_service
        self.llm_service = llm_service

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

    async def get_research(self, media_name: str, media_id: int) -> Dict[str, Any]:
        """
        Generates research content for a given media item, creates an embedding,
        and saves it to the MediaResearch table.

        Args:
            media_name (str): The name of the media to research.
            media_id (int): The ID of the Media record to associate with this research.

        Returns:
            Dict[str, Any]: A dictionary indicating success or failure,
                            and potentially the created research entry ID and text.
        """
        self.logger.info(f"Starting research generation for media: '{media_name}' (ID: {media_id})")

        # 1. Get prompt template
        research_prompt_template = self.settings_service.get("app", "default_research_prompt")
        if not research_prompt_template:
            self.logger.error("Default research prompt template not found in settings.")
            return {"success": False, "message": "Default research prompt template not configured."}

        # 2. Render prompt
        try:
            rendered_prompt = self.llm_service.get_research_prompt(media_name=media_name)
        except Exception as e:
            self.logger.error(f"Error rendering research prompt for '{media_name}': {e}", exc_info=True)
            return {"success": False, "message": f"Error rendering research prompt: {e}"}
        
        self.logger.debug(f"Generated research prompt for '{media_name}'.")

        # 3. Call LLM to generate research content
        llm_response = await self.llm_service.generate_content(prompt_data=rendered_prompt)

        if not llm_response.get("success"):
            msg = llm_response.get("message", "LLM content generation failed.")
            self.logger.error(f"LLM failed to generate research content for '{media_name}': {msg}")
            return {"success": False, "message": msg}

        research_text = llm_response.get("content")
        if not research_text or not isinstance(research_text, str):
            self.logger.error(f"LLM generated invalid or empty research content for '{media_name}'.")
            return {"success": False, "message": "LLM generated invalid or empty content."}
        
        self.logger.info(f"Successfully generated research content for '{media_name}'. Length: {len(research_text)}")

        # 4. Create embedding for the research text
        embedding = self.create_embedding(research_text)
        if embedding is None:
            self.logger.error(f"Failed to create embedding for research text of '{media_name}'.")
            return {"success": False, "message": "Failed to create embedding for research content."}
        
        self.logger.info(f"Successfully created embedding for research content of '{media_name}'.")

        # 5. Save to MediaResearch table (Upsert: update if exists, else create)
        try:
            research_entry, created = MediaResearch.get_or_create(
                media_id=media_id,
                defaults={'research': research_text, 'embedding': embedding}
            )
            if not created: # If it existed, update it
                research_entry.research = research_text
                research_entry.embedding = embedding
                research_entry.updated_at = datetime.now()
                research_entry.save()
            self.logger.info(f"Successfully {'created' if created else 'updated'} research data in MediaResearch for media_id {media_id} (Entry ID: {research_entry.id}).")
            return {"success": True, "message": "Research data generated and saved.", "research_id": research_entry.id, "research_text": research_text}
        except Exception as e:
            self.logger.error(f"Database error saving MediaResearch for media_id {media_id}: {e}", exc_info=True)
            return {"success": False, "message": f"Database error: {e}"}