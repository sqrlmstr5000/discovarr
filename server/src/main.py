from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from fastapi.responses import FileResponse
from discovarr import Discovarr
from pydantic import BaseModel
import json
import logging # Keep logging import
from datetime import datetime # Import datetime
import logging.config
import sys
import os
import uvicorn
import asyncio

from services.models import WatchHistoryCreateRequest # Import new Pydantic models
# This is your original application, now specifically for API routes
api_app = FastAPI(
    title="Discovarr API",
    # OpenAPI docs will be available at /api/docs, /api/redoc etc.
)

# Setup Logging
loglevel_str = os.environ.get('LOGLEVEL', default='DEBUG')
loglevel = getattr(logging, loglevel_str, "DEBUG")
LOGGING_CONFIG = { 
    'version': 1,
    'formatters': { 
        'standard': { 
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': { 
        'default': { 
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': loglevel,
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default'],
            'level': loglevel,
        },
        # Specific loggers can be added here if they need a different level
        # or different handlers than the root logger.
        # For example, to set 'apscheduler' to WARNING level:
        # 'apscheduler': {
        # 'handlers': ['default'],
        # 'level': 'WARNING',
        # 'propagate': False, # Or True, depending on desired behavior
        # },
    },
}

# Initialize logging configuration
logging.config.dictConfig(LOGGING_CONFIG)

# Create logger for the main application module
logger = logging.getLogger(__name__)

# --- Create the main root application ---
# This 'app' will be the one Uvicorn runs.
app = FastAPI(title="Discovarr")

# Add middleware to log all requests to the root app
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response
    
# Global error handling for the root app
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error: {exc}", exc_info=True)
    # Consider returning JSONResponse for consistency if preferred:
    # from fastapi.responses import JSONResponse
    # return JSONResponse(status_code=500, content={"detail": str(exc)})
    return {"detail": str(exc)}

# Setup CORS for the api_app
origins = ["*"] # Define origins for CORS
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CustomPromptRequest(BaseModel):
    prompt: str
    media_name: Optional[str] = None
    name: Optional[str] = None # Add name field
    favorites_option: Optional[str] = None

class ScheduleSearchRequest(BaseModel):
    prompt: Optional[str] = None
    year: Union[int|str] = "*"
    month: Union[int|str] = "*" 
    hour: Union[int|str] = "*"
    day: Union[int|str] = "*"
    minute: Union[int|str] = "*"
    day_of_week: Optional[str] = "*"
    enabled: Optional[bool] = True

class RequestMediaBody(BaseModel):
    media_type: str
    quality_profile_id: Optional[int] = None
    save_default: Optional[bool] = False

class SettingUpdateRequest(BaseModel):
    """Request model for updating a setting."""
    value: Optional[str] = None

class SettingResponse(BaseModel):
    """Response model for a setting."""
    name: str
    group: str
    value: Optional[str]
    default: Optional[str]
    type: str
    description: Optional[str]

class ScheduleSearchResponse(BaseModel):
    id: str
    success: bool
    message: str

class JobTriggerResponse(BaseModel):
    success: bool
    message: str

class MediaResearchResponse(BaseModel):
    """Response model for a MediaResearch entry."""
    id: int # Primary key of MediaResearch
    media_id: Optional[int] = None # The media_id (PK of Media table)
    research: str
    media_title: Optional[str] = None # Add media_title for display
    #created_at: datetime
    #updated_at: datetime

class PromptPreviewRequest(BaseModel):
    limit: int
    media_name: Optional[str] = None
    prompt: Optional[str] = None

class ResearchPromptPreviewRequest(BaseModel):
    media_name: Optional[str] = None
    prompt: Optional[str] = None # This will be the template_string

class ResearchRequest(BaseModel):
    media_name: str
    media_id: Optional[int] = None
    prompt: Optional[str] = None # This will be the template_string

class MediaSearchResultItem(BaseModel):
    title: Optional[str] = None
    media_id: Optional[int] = None # Corresponds to Media.id (Primary Key)
    media_type: Optional[str] = None


# Store single instance
_discovarr_instance = None

def get_discovarr() -> Discovarr:
    """
    Dependency injection for the Discovarr class.
    Returns the same instance for the entire application lifetime.
    """
    global _discovarr_instance
    if _discovarr_instance is None:
        _discovarr_instance = Discovarr()
        logger.info("Initialized Discovarr instance")
    return _discovarr_instance

@app.on_event("startup")
async def startup_event():
    """
    Tasks to run when the application starts.
    This includes initializing Discovarr and starting the scheduler.
    """
    logger.info("Application startup: Initializing Discovarr and starting scheduler...")
    logger.info(f"Log level set to: {loglevel}")
    current_loop_id_at_startup = id(asyncio.get_event_loop())
    logger.info(f"FastAPI startup_event running in event loop ID: {current_loop_id_at_startup}")
    discovarr_instance = get_discovarr() # Ensures Discovarr and its scheduler are initialized
    if discovarr_instance and hasattr(discovarr_instance, 'scheduler') and \
       hasattr(discovarr_instance.scheduler, 'scheduler') and \
       not discovarr_instance.scheduler.scheduler.running:
        try:
            # Start the underlying APScheduler
            discovarr_instance.scheduler.scheduler.start()
            logger.info("APScheduler (AsyncIOScheduler) started successfully.")
            # Now load the schedules from the database into the started scheduler
            discovarr_instance.scheduler.load_schedules()
            logger.info("Schedules loaded into APScheduler.")
        except Exception as e:
            logger.error(f"Failed to start APScheduler: {e}", exc_info=True)

@api_app.get("/users")
async def get_all_provider_users(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to retrieve all users from enabled library providers (Jellyfin, Plex, Trakt).
    """
    users = discovarr.get_users()
    if users is None:
        # This could happen if no providers are configured or if there's an API error
        raise HTTPException(status_code=503, detail="No library providers enabled or error fetching users.")
    return users

@api_app.get("/sync_watch_history")
async def sync_watch_history(
    limit: Optional[int] = None,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to retrieve recently watched items from the Jellyfin API.
    """
    return await discovarr.sync_watch_history()

# --- Trakt Endpoints ---
@api_app.post("/trakt/authenticate")
async def trakt_authenticate_endpoint(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to initiate Trakt authentication.
    This will typically involve device authentication flow.
    """
    logger.info("Received request to authenticate Trakt.")
    if not discovarr.trakt:
        raise HTTPException(status_code=503, detail="Trakt service is not configured or enabled.")
    
    # The _authenticate method in TraktProvider is blocking.
    # Running it in a thread to avoid blocking FastAPI's event loop for long.
    # However, the user interaction (entering code) is inherently blocking for the user.
    auth_result = await asyncio.to_thread(discovarr.trakt_authenticate)
    
    if auth_result.get("success"):
        return {
            "status": "success", 
            "message": auth_result.get("message", "Trakt authentication process initiated. Check server logs for user code and verification URL."),
            "user_code": auth_result.get("user_code"),
            "verification_url": auth_result.get("verification_url")
        }
    else:
        # The TraktProvider's _authenticate method logs specifics.
        # This might mean auth was already in progress, or an error occurred.
        # The message from auth_result should provide more context.
        detail_message = auth_result.get("message", "Trakt authentication failed or was already in progress. Check server logs.")
        raise HTTPException(status_code=500, detail=detail_message)

###
# Gemini
###

@api_app.get("/gemini/similar_media/search/{search_id}")
async def gemini_similar_media_by_search(
    search_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Run a saved search by ID.
    """
    logger.info(f"Running saved search with ID: {search_id}")
    try:
        search = discovarr.db.get_search(search_id)
        if not search:
            raise HTTPException(status_code=404, detail=f"Search with ID {search_id} not found")
        
        result = await discovarr.get_similar_media(media_name=None, custom_prompt=search["prompt"], search_id=search_id)
        
        if isinstance(result, dict) and result.get('success') is False:
            status_code = result.get('status_code', 500)
            message = result.get('message', f"Unknown error from LLM provider during saved search {search_id}.")
            logger.error(f"Error running saved search {search_id}: {message} (Status: {status_code})")
            raise HTTPException(status_code=status_code, detail=message)
        
        return result # List of suggestions
    except HTTPException: # Re-raise if it's already an HTTPException
        raise
    except Exception as e:
        logger.error(f"Error running saved search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/gemini/similar_media/{media_name}")
async def gemini_similar_media(
    media_name: str,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to find media similar to the given media name using the Gemini API.
    Used for the default recently watched search.
    """
    result = await discovarr.get_similar_media(media_name)
    if isinstance(result, dict) and result.get('success') is False:
        status_code = result.get('status_code', 500)
        message = result.get('message', f"Error processing media name {media_name}.")
        logger.error(f"Error for media name {media_name}: {message} (Status: {status_code})")
        raise HTTPException(status_code=status_code, detail=message)
    return result # List of suggestions



@api_app.post("/gemini/similar_media_custom")
async def gemini_similar_media_with_prompt(
    request: CustomPromptRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to find media similar to the given media name using the Gemini API with a custom prompt.
    Used for the search box in the UI.
    
    Args:
        request: Request body containing the prompt
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Received custom prompt request: {request.prompt}")
    try:
        result = await discovarr.get_similar_media(media_name=request.media_name, custom_prompt=request.prompt)
        
        if isinstance(result, dict) and result.get('success') is False: # Check our error structure
            status_code = result.get('status_code', 500)
            message = result.get('message', "Unknown error from LLM provider.")
            logger.error(f"Error from get_similar_media: {message} (Status: {status_code})")
            raise HTTPException(status_code=status_code, detail=message)
        
        logger.info(f"Successfully processed custom prompt")
        return result # This should be the list of suggestions
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Error processing custom prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/research")
async def research_media_endpoint(
    request: ResearchRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to generate research for a given media item.
    """
    logger.info(f"Received research request for media: '{request.media_name}' (ID: {request.media_id})")
    try:
        result = await discovarr.generate_research(media_name=request.media_name, media_id=request.media_id, template_string=request.prompt)
        
        if not result.get("success"):
            status_code = result.get("status_code", 500) # Default to 500 if not specified
            message = result.get("message", "Unknown error during research generation.")
            logger.error(f"Error generating research for '{request.media_name}': {message} (Status: {status_code})")
            raise HTTPException(status_code=status_code, detail=message)
        
        logger.info(f"Successfully generated research for '{request.media_name}'.")
        return result # Contains success, message, research_id, research_text
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing research request for '{request.media_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    
@api_app.get("/research", response_model=List[MediaResearchResponse])
async def get_research_endpoint(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to retrieve all existing research data entries.
    """
    logger.info("Received request to get all research entries.")
    try:
        research_data = discovarr.get_all_research()
        return research_data # This is already a list of dictionaries
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving research: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while retrieving research: {str(e)}")
    
@api_app.delete("/research/{research_id}")
async def delete_media_research_endpoint(
    research_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Delete a specific MediaResearch entry by its ID.
    """
    logger.info(f"Received request to delete MediaResearch entry with ID: {research_id}")
    try:
        result = discovarr.delete_media_research(research_id)
        if not result.get("success"):
            status_code = result.get("status_code", 500) # Default to 500 if not specified
            # If status_code is 404, it means not found.
            raise HTTPException(status_code=status_code, detail=result.get("message"))
        
        # On successful deletion
        return {"status": "success", "message": result.get("message")}
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting MediaResearch entry {research_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while deleting MediaResearch entry {research_id}.")

@api_app.post("/research/prompt/preview")
async def preview_research_prompt_endpoint(
    request: ResearchPromptPreviewRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Previews a rendered research prompt based on the provided template and media name.
    """
    logger.info(f"Generating research prompt preview with data: {request.model_dump_json(indent=2)}")
    try:
        # The get_research_prompt method in Discovarr handles the case where request.prompt (template_string) is None
        # by attempting to use the default research prompt from settings.
        # It also has its own try-except that returns an error message string if rendering fails.
        rendered_prompt = discovarr.get_research_prompt(
            media_name=request.media_name,
            template_string=request.prompt
        )
        # If get_research_prompt returns an error message string, pass it through.
        return {"result": rendered_prompt}
    except Exception as e:
        # This outer try-except catches unexpected errors in this endpoint logic itself,
        # or if get_research_prompt were to raise an exception instead of returning an error string.
        logger.error(f"Error generating research prompt preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while generating research prompt preview: {str(e)}")

###
# Ollama
# LLM (Combined)

###
# Ollama
# LLM (Combined)
###
@api_app.get("/llm/models")
async def get_llm_provider_models(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to retrieve available models from all enabled LLM providers.
    """
    logger.info("Received request to list models from all enabled LLM providers.")
    models = await discovarr.get_llm_models()
    if models is None:
        # This could happen if LLMService is not initialized or if there's an error during listing
        raise HTTPException(status_code=503, detail="LLM service unavailable or error fetching models.")
    return models

@api_app.post("/request/{tmdb_id}")
async def request_media(
    tmdb_id: str,
    request_body: RequestMediaBody,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Endpoint to request a specific media item using the TMDB ID.
    
    Args:
        tmdb_id: The TMDB ID of the media item
        request_body: Request body containing media_type, quality_profile_id, and save_default
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Requesting media: {tmdb_id} with body: {request_body.model_dump_json(indent=2)}")
    try:
        # Assuming discovarr.request_media now returns an APIResponse object
        api_response = discovarr.request_media(
            tmdb_id, request_body.media_type, request_body.quality_profile_id, request_body.save_default
        )

        if api_response.success:
            logger.info(f"Successfully processed media request for {tmdb_id}. Response data: {json.dumps(api_response.data, indent=2) if api_response.data else 'No data'}")
            # On success, the actual data from Sonarr/Radarr is in api_response.data
            return api_response.data 
        else:
            # Handle failure based on the APIResponse
            error_message = api_response.message or "Unknown error during media request."
            details = api_response.error # This is a Dict[str, Any]
            full_error_detail = error_message
            status_code = api_response.status_code if isinstance(api_response.status_code, int) else 500
            logger.error(f"Error requesting media {tmdb_id}: Status {status_code}, Detail: {details}")
            raise HTTPException(status_code=status_code, detail=details)

    except Exception as e:
        # Catch any other unexpected exceptions during the endpoint logic itself
        logger.error(f"Unexpected error in request_media endpoint for {tmdb_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/test")
async def test():
    """
    Endpoint to find media similar to the given media name using the Gemini API.
    """
    with open("test.json", 'r') as file:
        data = json.load(file)
        return data
    return data

@api_app.get("/process")
async def process(discovarr: Discovarr = Depends()):
    """
    Main endpoint to process media requests and find similar media.
    """
    return await discovarr.process_watch_history()

@api_app.get("/media/active")
async def get_active_media(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get all non-ignored media entries from the database.
    """
    return discovarr.get_active_media()

@api_app.get("/media/ignored")
async def get_ignored_suggestions(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get all ignored media entries from the database.
    """
    return discovarr.get_ignored_suggestions()
@api_app.post("/media/{media_id}/toggle-ignore")
async def toggle_ignore_status(
    media_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Toggle the ignore status for a specific media entry.
    """
    return discovarr.toggle_ignore_status(media_id)

@api_app.put("/media/{media_id}/ignore")
async def update_ignore_status(
    media_id: int,
    ignore: bool,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Update the ignore status for a specific media entry.
    """
    return discovarr.update_ignore_status(media_id, ignore)

@api_app.delete("/media/{media_id}")
async def delete_media_item(
    media_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Delete a specific media entry from the database.
    
    Args:
        media_id: The ID of the media item to delete.
        discovarr: Discovarr instance from dependency injection.
    """
    logger.info(f"Attempting to delete media item with ID: {media_id}")
    try:
        if discovarr.db.delete_media(media_id):
            return {"status": "success", "message": f"Media item {media_id} deleted successfully."}
        raise HTTPException(status_code=404, detail=f"Media item with ID {media_id} not found.")
    except Exception as e:
        logger.error(f"Error deleting media item {media_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/media/search", response_model=list[MediaSearchResultItem])
async def search_media_endpoint(
    query: str,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Search for media items in the database by a query string.
    Returns a list of items with title, media_id (tmdb_id), and media_type.
    """
    logger.info(f"Received media search request with query: '{query}'")
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty.")
    try:
        results = discovarr.search_media(query)
        return results
    except Exception as e:
        logger.error(f"Error during media search for query '{query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during media search: {str(e)}")



@api_app.get("/quality-profiles/{media_type}")
async def get_quality_profiles(
    media_type: str,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get quality profiles for a specific media type.
    
    Args:
        media_type (str): Type of media ('tv' or 'movie')
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Getting quality profiles for {media_type}")
    profiles = discovarr.get_quality_profiles(media_type)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No quality profiles found for {media_type}")
    return profiles



@api_app.get("/search/stat")
async def get_all_search_stats(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get token usage statistics for all searches.
    
    Args:
        discovarr: Discovarr instance from dependency injection
    """
    logger.info("Getting all search stats")
    try:
        return discovarr.db.get_search_stats()
    except Exception as e:
        logger.error(f"Error getting all search stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/search/stat/summary")
async def get_search_stat_summary(
    start_date: Optional[datetime] = None, # Add start_date parameter
    end_date: Optional[datetime] = None,   # Add end_date parameter
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get token usage statistics summary, optionally filtered by a date range.
    
    Args:
        start_date: Optional start date for filtering stats.
        end_date: Optional end date for filtering stats.
        discovarr: Discovarr instance from dependency injection.
    """
    logger.info(f"Getting search stat summary for range: {start_date} to {end_date}")
    try:
        return discovarr.get_search_stat_summary(start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"Error getting search stat summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/watch-history/grouped")
async def get_watch_history_grouped_endpoint(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get watch history grouped by user, optionally filtered by a date range.
    
    Args:
        start_date: Optional start date for filtering watch history.
        end_date: Optional end date for filtering watch history.
        discovarr: Discovarr instance from dependency injection.
    """
    logger.info(f"Getting grouped watch history for range: {start_date} to {end_date}")
    try:
        return discovarr.get_watch_history_grouped(start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"Error getting grouped watch history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_app.delete("/watch-history/all")
async def delete_all_watch_history_endpoint(
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Delete all watch history items from the database.
    """
    logger.info("Attempting to delete all watch history items.")
    try:
        result = discovarr.delete_all_watch_history()
        if not result.get("success"):
            # This case is less likely for 'delete all' unless there's a DB connection issue
            status_code = result.get("status_code", 500)
            raise HTTPException(status_code=status_code, detail=result.get("message"))
        return {"status": "success", "message": result.get("message")}
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting all watch history items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while deleting all watch history items.")
    
@api_app.post("/watch-history/import", status_code=201) # 201 Created for successful POST
async def create_watch_history_item_endpoint(
    request_data: WatchHistoryCreateRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Manually add or update a watch history item.
    This endpoint performs an upsert based on title and watched_by.
    """
    logger.info(f"Received request to create/update watch history item: {request_data.title}")
    try:
        result = await discovarr.add_watch_history_item_manual(request_data.model_dump())
        if not result.get("success"):
            status_code = result.get("status_code", 500)
            raise HTTPException(status_code=status_code, detail=result.get("message"))
        # For a true POST that creates, you might return the created object.
        # Since this is an upsert, a success message is fine.
        return result
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating/updating watch history item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@api_app.delete("/watch-history/{history_item_id}")
async def delete_watch_history_item_endpoint(
    history_item_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Delete a specific watch history item by its ID.
    """
    logger.info(f"Attempting to delete watch history item with ID: {history_item_id}")
    try:
        result = discovarr.delete_watch_history_item(history_item_id)
        if not result.get("success"):
            status_code = result.get("status_code", 404 if "not found" in result.get("message", "").lower() else 500)
            raise HTTPException(status_code=status_code, detail=result.get("message"))
        return {"status": "success", "message": result.get("message")}
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting watch history item {history_item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while deleting watch history item {history_item_id}.")
    
@api_app.get("/media/field/{col_name}")
async def get_media_field_values(
    col_name: str,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get unique values from a specific column in the media table.
    If the column contains comma-delimited strings, they will be split.

    Args:
        col_name (str): The name of the column to query for unique values
                        (e.g., 'media_type', 'title', 'networks', 'genres').
        discovarr: Discovarr instance from dependency injection.
    """
    logger.info(f"Getting unique media values for column: {col_name}")
    try:
        unique_values = discovarr.get_media_by_field(col_name)
        # The method already returns an empty list on error or if no data,
        # which is fine for a 200 OK response.
        return unique_values
    except Exception as e:
        logger.error(f"Error getting unique media values for column '{col_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while fetching unique values for column '{col_name}'.")

@api_app.get("/search")
async def get_searches(
    limit: int = 10,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get recent searches from the database.
    
    Args:
        limit: Maximum number of searches to return
        discovarr: Discovarr instance from dependency injection
    """
    return discovarr.get_searches(limit)

@api_app.get("/search/{search_id}")
async def get_search(
    search_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get a specific search by ID.
    
    Args:
        search_id: ID of the search to retrieve
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Getting search with ID: {search_id}")
    try:
        search = discovarr.db.get_search(search_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search not found")
        return search
    except Exception as e:
        logger.error(f"Error getting search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/search/prompt/preview")
async def preview_search_prompt(
    request: PromptPreviewRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Previews a rendered search prompt based on the provided template, limit, and media name.
    """
    logger.info(f"Generating prompt preview with data: {request.model_dump_json(indent=2)}")
    try:
        # The get_prompt method in Discovarr handles the case where request.prompt (template_string) is None
        # by attempting to use self.default_prompt.
        # It also has its own try-except that returns an error message string if rendering fails.
        rendered_prompt = discovarr.get_prompt(
            limit=request.limit,
            media_name=request.media_name,
            template_string=request.prompt,
        )
        # If get_prompt returns an error message string (e.g., "Error rendering prompt: ..."),
        # we pass it through in the response.
        return { "result": rendered_prompt }
    except Exception as e:
        # This outer try-except catches unexpected errors in this endpoint logic itself,
        # or if get_prompt were to raise an exception instead of returning an error string.
        logger.error(f"Error generating prompt preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while generating prompt preview: {str(e)}")

@api_app.post("/search")
async def save_search(
    request: CustomPromptRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Save a search prompt to the database.
    
    Args:
        request: Request body containing the prompt
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Saving search prompt: {request.prompt}")
    try:
        search = discovarr.save_search(prompt=request.prompt, name=request.name, favorites_option=request.favorites_option)
        logger.info(f"Saved search with ID: {search}")
        if not search:
            raise HTTPException(status_code=500, detail="Failed to save search")
        return search
    except Exception as e:
        logger.error(f"Error saving search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.put("/search/{search_id}")
async def update_search(
    search_id: int,
    request: CustomPromptRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Update an existing search prompt in the database.
    
    Args:
        search_id: ID of the search to update
        request: Request body containing the updated prompt
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Updating search {search_id} with prompt: {request.prompt}")
    try:
        success = discovarr.update_search(search_id, request.prompt, request.name, favorites_option=request.favorites_option)
        if not success:
            raise HTTPException(status_code=404, detail="Search not found")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.delete("/search/{search_id}")
async def delete_search(
    search_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Delete a search and its associated media entries from the database.
    
    Args:
        search_id: ID of the search to delete
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Deleting search with ID: {search_id}")
    try:
        if discovarr.delete_search(search_id):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Search not found")
    except Exception as e:
        logger.error(f"Error deleting search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/search/{search_id}/stat")
async def get_search_stats(
    search_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get token usage statistics for a specific search.
    
    Args:
        search_id: ID of the search
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Getting stats for search ID: {search_id}")
    try:
        stats = discovarr.db.get_search_stats(search_id)
        if not stats:
            return []
        return stats
    except Exception as e:
        logger.error(f"Error getting search stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/schedule/search/{search_id}")
async def get_search_schedule(
    search_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Get the schedule for a specific search.
    
    Args:
        search_id: ID of the search
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Getting schedule for search ID: {search_id}")
    try:
        schedule = discovarr.db.get_schedule_by_search_id(search_id)
        if not schedule:
            return None
        return schedule
    except Exception as e:
        logger.error(f"Error getting schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.put("/schedule/search/{search_id}")
async def update_search_schedule(
    search_id: int,
    request: ScheduleSearchRequest,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Update or create a schedule for a search.
    
    Args:
        search_id: ID of the search
        request: Request body containing schedule parameters
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Updating schedule for search ID: {search_id}")
    try:
        schedule_data = {
            "year": request.year,
            "month": request.month,
            "hour": request.hour,
            "minute": request.minute,
            "day": request.day,
            "day_of_week": request.day_of_week,
            "enabled": request.enabled,
            "kwargs": json.dumps({
                "media_name": None,
                "search_id": search_id,
                "custom_prompt": request.prompt
            })
        }
        
        schedule = discovarr.db.get_schedule_by_search_id(search_id)
        schedule_id = None
        if schedule:
            schedule_id = discovarr.db.update_schedule(search_id=search_id, update_data=schedule_data)
        else:
            func_name = "get_similar_media"
            job_id = f"{func_name}_{search_id}"
            schedule_id = discovarr.db.add_schedule(
                search_id=search_id,
                job_id=job_id,
                func_name=func_name,
                **schedule_data,
            )
        if not schedule_id:
            raise HTTPException(status_code=500, detail="Failed to update schedule")
            
        # Reload schedules to pick up the updated schedule
        discovarr.scheduler.load_schedules()
            
        return {"success": True, "schedule_id": schedule_id}
    except Exception as e:
        logger.error(f"Error updating schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.delete("/schedule/search/{search_id}")
async def delete_search_schedule(
    search_id: int,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Delete the schedule for a search.
    
    Args:
        search_id: ID of the search
        discovarr: Discovarr instance from dependency injection
    """
    logger.info(f"Deleting schedule for search ID: {search_id}")
    try:
        if discovarr.db.delete_schedule_by_search_id(search_id=search_id):
            # Reload schedules to remove the deleted schedule
            discovarr.scheduler.load_schedules()
            return {"success": True}
        return {"success": False}
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/schedule/job/{job_id}/trigger", response_model=JobTriggerResponse)
async def trigger_job_endpoint(
    job_id: str,
    discovarr: Discovarr = Depends(get_discovarr),
):
    """
    Manually trigger a scheduled job to run immediately.
    """
    logger.info(f"Received request to trigger job: {job_id}")
    try:
        result = discovarr.trigger_scheduled_job(job_id)
        if not result["success"]:
            # Determine appropriate status code based on message
            if "not found" in result["message"].lower():
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                # For other failures, trigger_job_now in scheduler logs details
                raise HTTPException(status_code=500, detail=result["message"])
        return result
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error while trying to trigger job '{job_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while triggering job '{job_id}'.")



# Settings management endpoints
@api_app.get("/settings")
async def get_all_settings(
    discovarr: Discovarr = Depends(get_discovarr),
) -> Dict[str, Dict[str, Any]]:
    """
    Get all settings grouped by their groups.
    """
    return discovarr.settings.get_all()

@api_app.get("/settings/{group}")
async def get_settings_by_group(
    group: str,
    discovarr: Discovarr = Depends(get_discovarr),
) -> Dict[str, Any]:
    """
    Get all settings in a group.
    """
    settings = discovarr.settings.get_settings_by_group(group)
    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings group {group} not found")
    return settings

@api_app.put("/settings/{group}/{name}")
async def update_setting(
    group: str,
    name: str,
    request: SettingUpdateRequest,
    discovarr: Discovarr = Depends(get_discovarr),
) -> Dict[str, str]:
    """
    Update a setting value.
    """
    success = discovarr.settings.set(group, name, request.value)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to update setting {group}.{name}")
    return {"status": "success", "message": f"Setting {group}.{name} updated successfully"}

@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on application shutdown.
    """
    global _discovarr_instance
    if _discovarr_instance:
        if hasattr(_discovarr_instance, 'scheduler') and \
           hasattr(_discovarr_instance.scheduler, 'scheduler') and \
           _discovarr_instance.scheduler.scheduler.running:
            logger.info("Shutting down APScheduler (AsyncIOScheduler)...")
            # The shutdown method in your Schedule class handles scheduler.shutdown(wait=False)
            _discovarr_instance.scheduler.shutdown() 
        _discovarr_instance = None
        logger.info("Cleaned up Discovarr instance")

# Mount the API application under the /api path prefix
app.mount("/api", api_app)

# Mount the /cache directory to serve cached images
cache_dir = Path("/cache")
if cache_dir.is_dir(): # Dockerfile creates this, so it should exist
    app.mount("/cache", StaticFiles(directory=cache_dir), name="cache")
else:
    logger.warning(f"Cache directory {cache_dir} not found. /cache endpoint will not be available.")

# Mount static files for the frontend (Vue.js app)
# This assumes your Dockerfile copies the client's 'dist' output to 'server/static'
# and main.py is in 'server/src/'
static_files_dir = Path(__file__).parent.parent / "static"

# Serve the 'assets' directory (JS, CSS, images from Vite build)
assets_sub_dir = static_files_dir / "assets"
if assets_sub_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_sub_dir), name="vite_assets")
else:
    logger.warning(f"Vite assets directory {assets_sub_dir} not found. Frontend assets might not load.")

@app.get("/logo.png", include_in_schema=False)
async def logo():
    file_path = static_files_dir / "logo.png"
    if file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="logo.png not found")

# Add other root static files here if needed, e.g., manifest.json, robots.txt, etc.

# Catch-all route to serve index.html for SPA routing
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_vue_app(request: Request, full_path: str):
    index_html_path = static_files_dir / "index.html"
    if not index_html_path.is_file():
        logger.error(f"SPA index.html not found at {index_html_path}")
        raise HTTPException(status_code=500, detail="SPA frontend is not built or not found.")
    return FileResponse(index_html_path)
