import logging
import json
from typing import List, Optional, Dict, Any
from jinja2 import Template
from datetime import datetime

from .settings import SettingsService
from .llm import LLMService
from .database import Database # Import Database for type hinting
from .models import MediaResearch, MediaResearchEmbedding # Import MediaResearch model
from providers.gemini import GeminiProvider # For checking provider name
from providers.ollama import OllamaProvider # For checking provider name

class ResearchService:
    """
    A service to handle text assimilation tasks, primarily creating embeddings.
    """

    def __init__(self,
                 settings_service: SettingsService,
                 llm_service: LLMService,
                 db_service: Database): # Removed model_name parameter
        """
        Initializes the ResearchService.

        Args:
            settings_service (SettingsService): Instance of the settings service.
            llm_service (LLMService): Instance of the LLM service.
            db_service (Database): Instance of the database service.
        """
        self.logger = logging.getLogger(__name__)
        self.settings_service = settings_service
        self.llm_service = llm_service
        self.db = db_service # Store the database service instance

    async def get_research_embedding(self, text: str) -> Optional[List[float]]:
        """
        Creates an embedding for the given text using the LLMService.
        """
        if not self.llm_service:
            self.logger.error("LLMService is not loaded. Cannot create embedding.")
            return None

        llm_embedding_model_name = None
        if self.llm_service.enabled_llm_provider_names:
            first_provider_name = self.llm_service.enabled_llm_provider_names[0]
            if first_provider_name == GeminiProvider.PROVIDER_NAME:
                llm_embedding_model_name = self.settings_service.get("gemini", "embedding_model")
                llm_embedding_dimensions = self.settings_service.get("gemini", "embedding_dimensions")
            elif first_provider_name == OllamaProvider.PROVIDER_NAME:
                llm_embedding_model_name = self.settings_service.get("ollama", "embedding_model")
                llm_embedding_dimensions = self.settings_service.get("ollama", "embedding_dimensions")
            
            if not llm_embedding_model_name or not llm_embedding_dimensions:
                self.logger.error(
                    f"Embedding model name or dimensions not configured for the primary LLM provider '{first_provider_name}'."
                )
                return None
        else:
            self.logger.error("No LLM providers enabled. Cannot generate embedding via LLMService.")
            return None

        try:
            self.logger.debug(f"Requesting embedding via LLMService with model: {llm_embedding_model_name} for text.")
            # The model parameter for llm_service.generate_embedding is the specific model name for the provider.
            embedding = await self.llm_service.generate_embedding(text_content=text.strip(), model=llm_embedding_model_name, )
            return embedding # LLMService.generate_embedding already returns List[float] or None
        except Exception as e:
            self.logger.error(f"Error creating embedding via LLMService: {e}", exc_info=True)
            return None

    async def generate_research(self, media_name: str, media_id: Optional[int] = None, template_string: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates research content for a given media item, creates an embedding,
        and saves it to the MediaResearch table using the LLMService for embeddings.

        Args:
            media_name (str): The name of the media to research.
            media_id (int): The ID of the Media record to associate with this research.

        Returns:
            Dict[str, Any]: A dictionary indicating success or failure,
                            and potentially the created research entry ID and text.
        """
        self.logger.info(f"Starting research generation for media: '{media_name}' (ID: {media_id})")

        # 1. Get prompt template
        if not template_string:
            research_prompt_template = self.settings_service.get("app", "default_research_prompt")
            if not research_prompt_template:
                self.logger.error("Default research prompt template not found in settings.", exc_info=True)
                return {"success": False, "message": "Default research prompt template not configured."}
        else:
            research_prompt_template = template_string

        # 2. Render prompt
        try:
            rendered_prompt = self.llm_service.get_research_prompt(media_name=media_name, template_string=research_prompt_template)
        except Exception as e:
            self.logger.error(f"Error rendering research prompt for '{media_name}': {e}", exc_info=True)
            return {"success": False, "message": f"Error rendering research prompt: {e}"}
        
        self.logger.debug(f"Generated research prompt for '{media_name}'.")
        self.logger.debug(f"Rendered Prompt: {rendered_prompt}")

        # 3. Call LLM to generate research content
        ref = {
            "method": "research",
            "media_name": media_name
        }
        llm_response = await self.llm_service.generate_content(
            prompt_data=rendered_prompt,
            reference=json.dumps(ref),
        )

        if not llm_response.get("success"):
            msg = llm_response.get("message", "LLM content generation failed.")
            self.logger.error(f"LLM failed to generate research content for '{media_name}': {msg}")
            return {"success": False, "message": msg}

        research_text = llm_response.get("content")
        if not research_text or not isinstance(research_text, str):
            self.logger.error(f"LLM generated invalid or empty research content for '{media_name}'.", exc_info=True)
            return {"success": False, "message": "LLM generated invalid or empty content."}

        self.logger.info(f"Successfully generated research content for '{media_name}'. Length: {len(research_text)}")

        # 4. Save to MediaResearch table (Upsert: update if exists, else create)
        research_entry = None # Initialize research_entry
        created = False # Initialize created
        try:
            if media_id is not None:
                # Enforce a one-to-one relationship for now. I could see allowing a research history in the future.
                research_entry, created = MediaResearch.get_or_create(
                    media_id=media_id, # Use media_id for lookup if it's provided
                    defaults={'research': research_text, 'title': media_name} # No embedding here
                )
                if not created: # If it existed, update it
                    research_entry.research = research_text
                    research_entry.updated_at = datetime.now()
                    research_entry.save()
            else:
                # If media_id is None, always create a new entry
                research_entry = MediaResearch.create(
                    research=research_text, title=media_name, media_id=None
                )
                self.logger.info(f"Successfully created new research data (no media_id) for title '{media_name}' (Entry ID: {research_entry.id}).")
                return {"success": True, "message": "Research data generated and saved (no media association).", "research_id": research_entry.id, "research_text": research_text}
            
            self.logger.info(f"Successfully {'created' if created else 'updated'} MediaResearch entry for '{media_name}' (ID: {research_entry.id}).")
        except Exception as e:
            self.logger.error(f"Database error saving MediaResearch for media_id {media_id}: {e}", exc_info=True)
            return {"success": False, "message": f"Database error: {e}"}
        
        # 5. Create embedding and save to MediaResearchEmbedding table
        try:
            if MediaResearchEmbedding.table_exists():
                embedding = await self.get_research_embedding(research_text)
                if embedding:
                    self.logger.info(f"Successfully created embedding for research content of '{media_name}'.")
                    MediaResearchEmbedding.insert(
                        mediaresearch=research_entry, # Link to the MediaResearch entry
                        embedding=embedding
                    ).on_conflict(
                        conflict_target=[MediaResearchEmbedding.mediaresearch], 
                        update={MediaResearchEmbedding.embedding: embedding}
                    ).execute()
                    self.logger.info(f"Successfully saved/updated embedding in MediaResearchEmbedding for MediaResearch ID {research_entry.id}.")
                else:
                    self.logger.warning(f"Failed to generate embedding for '{media_name}'. Research text saved, but embedding is not.")
        except Exception as e:
            self.logger.error(f"Database error saving MediaResearchEmbedding for media_id {media_id}: {e}", exc_info=True)
            return {"success": False, "message": f"Database error saving embedding: {e}"}
        
        # If we've reached here, all operations (or the ones possible) were successful
        return {
            "success": True, 
            "message": "Research data generated and saved successfully.", 
            "research_id": research_entry.id if research_entry else None, 
        }