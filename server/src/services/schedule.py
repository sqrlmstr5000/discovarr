import logging
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
import json

class Schedule:
    """
    A class to handle scheduling tasks using APScheduler with cron triggers.
    """

    def __init__(self, db):
        """
        Initialize the scheduler with a background scheduler.

        Args:
            db: Database instance for loading and saving schedules
        """
        self.logger = logging.getLogger(__name__)
        # Initialize AsyncIOScheduler. It will use asyncio.get_event_loop() by default
        # when start() is called if no explicit loop is provided.
        self.scheduler = AsyncIOScheduler()
        self.db = db
        # self.scheduler.start() will be called from the main application startup

    def load_schedules(self) -> None:
        """
        Load all schedules from the database and add them to the scheduler.
        Each schedule must have a corresponding function in the function_map.
        """
        try:
            # Clear existing jobs before loading from database
            self.remove_all_jobs()
            
            schedules = self.db.get_schedules()
            self.logger.info(f"Loading {len(schedules)} schedules from database")
            
            for schedule in schedules:
                self.logger.info(f"Loading schedule {schedule['job_id']}")
                if not schedule['enabled']:
                    self.logger.debug(f"Skipping disabled schedule {schedule['job_id']}")
                    continue

                # Parse args and kwargs from JSON
                try:
                    args = json.loads(schedule['args']) if schedule['args'] else []
                    kwargs = json.loads(schedule['kwargs']) if schedule['kwargs'] else {}
                    kwargs = json.loads(kwargs) if isinstance(kwargs, str) else kwargs
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON for args in schedule {schedule['job_id']}")
                    continue

                self.logger.debug(f"Parsed args: (type: {type(args)}) {args}, kwargs (type: {type(kwargs)}): {kwargs}")

                # Get the function from the function map. Runtime kwargs from DB will be passed by APScheduler.
                func = self.get_function(schedule['func_name'])
                if not func:
                    self.logger.error(f"Function {schedule['func_name']} not found for schedule {schedule['job_id']}")
                    continue

                # Add the job
                job = self.add_job(
                    job_id=schedule['job_id'],
                    func=func,
                    minute=schedule['minute'],
                    hour=schedule['hour'],
                    day=schedule['day'],
                    day_of_week=schedule['day_of_week'],
                    month=schedule['month'],
                    year=schedule['year'],
                    args=args,
                    kwargs=kwargs
                )
                
                if job:
                    self.logger.info(f"Successfully loaded schedule {job.id}")
                    self.logger.debug(f"Job details: {job}")
                    self.logger.info(f"Next run time for {job.id} is {job.next_run_time}")
                else:
                    self.logger.error(f"Failed to load schedule {schedule['job_id']}")

                self.logger.info(f"Loaded Job List: {self.get_all_jobs()}")

        except Exception as e:
            self.logger.error(f"Error loading schedules: {e}", exc_info=True)

    def get_function(self, func_name: str) -> Optional[callable]:
        """
        Get the function to be called for a schedule.
        Override this method to provide your own function mapping.

        Args:
            func_name (str): Name of the function to get

        Returns:
            Optional[callable]: The function if found, None otherwise
        """
        # This should be overridden in a subclass to provide actual function mapping
        self.logger.warning(f"No function mapping provided for {func_name}")
        return None

    def add_job(self, 
                job_id: str,
                func: callable,
                minute: Optional[int] = None,
                hour: Optional[int] = None,
                day: Optional[str] = None,
                day_of_week: Optional[str] = None,
                month: Optional[str] = None,
                year: Optional[str] = None,
                args: Optional[list] = None,
                kwargs: Optional[dict] = None,
                replace_existing: bool = True) -> Optional[Job]:
        """
        Add a new job to the scheduler using cron trigger.

        Args:
            job_id (str): Unique identifier for the job
            func (callable): The function to be called
            year (Optional[str]): Year (4-digit year, range, or '*' for any)
            month (Optional[str]): Month (1-12, range, or '*' for any)
            hour (Optional[int]): Hour (0-23)
            minute (Optional[int]): Minute (0-59)
            day_of_week (Optional[str]): Day of week (0-6 or mon,tue,wed,thu,fri,sat,sun)
            args (Optional[list]): List of positional arguments to pass to the function
            kwargs (Optional[dict]): Dictionary of keyword arguments to pass to the function
            replace_existing (bool): Whether to replace if job already exists

        Returns:
            Optional[Job]: The scheduled job if successful, None otherwise
        """
        try:
            trigger = CronTrigger(
                minute=minute if minute is not None else '*',
                hour=hour if hour is not None else '*',
                day=day if day is not None else '*',
                day_of_week=day_of_week if day_of_week is not None else '*',
                month=month if month is not None else '*',
                year=year if year is not None else '*',
            )

            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args or [],
                kwargs=kwargs or {},
                replace_existing=replace_existing
            )
            
            self.logger.info(f"Added job {job_id} with schedule: minute={minute}, hour={hour}, day={day}, day_of_week={day_of_week}, month={month}, year={year}")
            return job
        except Exception as e:
            self.logger.error(f"Error adding job {job_id}: {e}")
            return None

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a job from the scheduler.

        Args:
            job_id (str): ID of the job to remove

        Returns:
            bool: True if job was removed successfully, False otherwise
        """
        try:
            self.scheduler.remove_job(job_id)
            self.logger.info(f"Removed job {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error removing job {job_id}: {e}")
            return False

    def remove_all_jobs(self) -> None:
        """
        Remove all jobs from the scheduler.
        """
        try:
            self.scheduler.remove_all_jobs()
            self.logger.info("Removed all jobs from scheduler")
        except Exception as e:
            self.logger.error(f"Error removing all jobs: {e}")

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by its ID.

        Args:
            job_id (str): ID of the job to get

        Returns:
            Optional[Job]: The job if found, None otherwise
        """
        try:
            return self.scheduler.get_job(job_id)
        except Exception as e:
            self.logger.error(f"Error getting job {job_id}: {e}")
            return None

    def get_all_jobs(self) -> list:
        """
        Get all scheduled jobs.

        Returns:
            list: List of all scheduled jobs
        """
        return self.scheduler.get_jobs()

    def pause_job(self, job_id: str) -> bool:
        """
        Pause a job by its ID.

        Args:
            job_id (str): ID of the job to pause

        Returns:
            bool: True if job was paused successfully, False otherwise
        """
        try:
            self.scheduler.pause_job(job_id)
            self.logger.info(f"Paused job {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error pausing job {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job by its ID.

        Args:
            job_id (str): ID of the job to resume

        Returns:
            bool: True if job was resumed successfully, False otherwise
        """
        try:
            self.scheduler.resume_job(job_id)
            self.logger.info(f"Resumed job {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error resuming job {job_id}: {e}")
            return False

    def shutdown(self):
        """
        Shut down the scheduler. Should be called when the application exits.
        """
        self.scheduler.shutdown()
        self.logger.info("Scheduler shut down")
