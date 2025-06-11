import logging
from typing import Optional, Dict, Any, Callable
from .schedule import Schedule
import json
from datetime import datetime
import asyncio 
class DiscovarrScheduler(Schedule):
    """
    Discovarr-specific implementation of the Schedule class.
    Maps schedule function names to actual Discovarr instance methods.
    """

    def __init__(self, db, discovarr_instance):
        """
        Initialize the Discovarr scheduler.

        Args:
            db: Database instance for loading and saving schedules
            discovarr_instance: Instance of Discovarr class containing the methods to be scheduled
        """
        self.discovarr = discovarr_instance
        super().__init__(db)
        self.logger = logging.getLogger(__name__)
        # Schedules will be loaded explicitly after the scheduler is started
        # in the main application's startup event.
            
    # def _setup_default_schedules(self):
    #     """
    #     Set up default schedules for common tasks.
    #     Only called if no schedules exist in the database.
    #     """
    #     # Process requests daily at 3 AM
    #     self.add_job(
    #         job_id="daily_process",
    #         func=self.discovarr.process_watch_history,
    #         hour=3,
    #         minute=0
    #     )
        
    #     # Check recently watched every 30 minutes
    #     self.add_job(
    #         job_id="check_recently_watched",
    #         func=self.discovarr.jellyfin_get_recently_watched,
    #         minute="*/30"
    #     )
        
    #     self.logger.info("Default schedules have been set up")

    def get_function(self, func_name: str) -> Optional[Callable]:
        """
        Map function names to actual Discovarr instance methods.
        The returned callable will receive args/kwargs from the Schedule table entry at runtime.
        
        Args:
            func_name (str): Name of the function to get

        Returns:
            Optional[callable]: The function if found, None otherwise
        """
        # Map of function names to actual methods
        if func_name == 'sync_watch_history':
            # This is now an async function. AsyncIOScheduler can call it directly.
            # Expects no runtime args/kwargs from the DB schedule for this specific task.
            return self.discovarr.sync_watch_history
        elif func_name == 'process_watch_history':
            # _create_process_function returns an async function directly.
            return self._create_process_function()
        elif func_name == 'jellyfin_get_recently_watched':
            # This is a synchronous function. AsyncIOScheduler will run it in an executor.
            # It expects runtime kwargs (e.g., {'limit': value}) from Schedule.kwargs in DB.
            def _jellyfin_runner(**runtime_kwargs):
                self.logger.info(f"Executing scheduled 'jellyfin_get_recently_watched' with runtime_kwargs: {runtime_kwargs}")
                return self.discovarr.jellyfin_get_recently_watched(limit=runtime_kwargs.get('limit'))
            return _jellyfin_runner
        elif func_name == 'get_active_media':
            # Synchronous, expects no runtime args/kwargs.
            return self.discovarr.get_active_media
        elif func_name == 'get_ignored_media':
            # Synchronous, expects no runtime args/kwargs.
            return self.discovarr.get_ignored_media
        elif func_name == 'get_similar_media':
            # _create_search_function returns an async function directly.
            # It expects runtime kwargs from Schedule.kwargs in DB.
            return self._create_search_function()
        else:
            self.logger.warning(f"No function mapping found for {func_name}")
            return None
        
    def trigger_job_now(self, job_id: str) -> bool:
        """
        Triggers a scheduled job to run immediately by modifying its next_run_time.

        Args:
            job_id: The ID of the job to trigger.

        Returns:
            True if the job was found and modified to run now, False otherwise.
        """
        job = self.get_job(job_id) # Uses get_job from the base Schedule class
        if job:
            try:
                # self.scheduler is the APScheduler BackgroundScheduler instance from the base Schedule class
                self.scheduler.modify_job(job_id, next_run_time=datetime.now(self.scheduler.timezone))
                self.logger.info(f"Job '{job_id}' (task: {job.name}) modified to run now.")
                return True
            except Exception as e:
                self.logger.error(f"Error modifying job '{job_id}' to run now: {e}", exc_info=True)
                return False
        else:
            self.logger.warning(f"Job '{job_id}' not found. Cannot trigger.")
            return False

    def _create_search_function(self) -> Callable:
        """
        Returns the asynchronous 'get_similar_media' task.
        AsyncIOScheduler will call this directly with kwargs from the schedule DB entry.

        Returns:
            Callable: An asynchronous function that AsyncIOScheduler can execute.
        """
        async def async_search_task(**runtime_job_kwargs):
            self.logger.info(f"Executing scheduled 'get_similar_media' with runtime_kwargs: {runtime_job_kwargs}")
            try:
                # These kwargs come from the 'kwargs' column of the Schedule table for this job
                media_name = runtime_job_kwargs.get('media_name') # Typically None for scheduled searches
                search_id = runtime_job_kwargs.get('search_id')
                custom_prompt = runtime_job_kwargs.get('custom_prompt')

                await self.discovarr.get_similar_media(
                    media_name=media_name,
                    search_id=search_id,
                    custom_prompt=custom_prompt
                )
            except Exception as e:
                self.logger.error(f"Error executing scheduled 'get_similar_media' with {runtime_job_kwargs}: {e}", exc_info=True)
                
        return async_search_task
    
    def _create_process_function(self) -> Callable:
        """
        Returns the asynchronous 'process_watch_history' task.
        AsyncIOScheduler will call this directly.

        Returns:
            Callable: An asynchronous function that AsyncIOScheduler can execute.
        """
        async def async_process_task(*args, **kwargs): # Accept args/kwargs passed by scheduler
            job_name = "process_watch_history"
            current_loop_id_in_task = id(asyncio.get_event_loop())
            self.logger.info(f"Scheduled task '{job_name}' running in event loop ID: {current_loop_id_in_task}")
            self.logger.info(f"Executing scheduled '{job_name}' with args: {args}, kwargs: {kwargs}")
            # Log if unexpected arguments are passed, as this task doesn't use them
            if args or kwargs:
                self.logger.warning(f"Scheduled '{job_name}' received unexpected arguments. Args: {args}, Kwargs: {kwargs}. These will be ignored by the task.")

            try:
                await self.discovarr.process_watch_history()
            except Exception as e:
                self.logger.error(f"Error executing scheduled '{job_name}': {e}", exc_info=True)
                
        return async_process_task
    
