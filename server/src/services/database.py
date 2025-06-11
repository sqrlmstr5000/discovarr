import importlib
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json
from peewee import fn, SqliteDatabase, JOIN
from playhouse.migrate import SqliteMigrator
from playhouse.shortcuts import model_to_dict
from .models import database, MODELS, Media, WatchHistory, Search, SearchStat, Schedule, Settings
from .backup import BackupService
from .settings import SettingsService # Import SettingsService
from .migrations import Migration

class Database:
    """
    A class to handle database operations using Peewee ORM.
    """

    def __init__(self, db_path: str, backup_on_upgrade: bool = True):
        """
        Initialize database configuration.

        Args:
            db_path (str): Path to the SQLite database file
            backup_on_upgrade (bool): Whether to backup the database before migrations.
        """
        self.backup_on_upgrade = backup_on_upgrade
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        self.backup_service = BackupService(logger=self.logger)
        
        # Initialize the database
        database.init(db_path, pragmas={
            "journal_mode": "wal",
            "temp_store":2,
            "synchronous": 1,
            "cache_size": 64000,
        })
        database.connect()
        
        # Create tables
        database.create_tables(MODELS)
        
        # Run migrations after creating tables
        self._run_migrations()
        self.logger.info("Successfully initialized database")

        self._add_default_tasks()

    def _run_migrations(self):
        """Run all pending database migrations"""
        try:
            migration = Migration(database)
            
            # Get all migration files
            migrations_dir = Path(__file__).parent / 'migrations'
            self.logger.info(f"Migrations Dir: {migrations_dir}")
            migration_files = sorted([
                f for f in migrations_dir.glob('[0-9]*.py')
                if f.stem != '__init__'
            ])

            latest_fs_migration_version = 0
            if migration_files:
                try:
                    latest_fs_migration_version = int(migration_files[-1].stem.split('_')[0])
                except (ValueError, IndexError):
                    self.logger.error("Could not determine latest migration version from filesystem.")
                    # Potentially raise an error or handle as appropriate

            current_db_version = migration.get_current_version()
            self.logger.info(f"Initial Database Version: {current_db_version}, Latest Filesystem Migration Version: {latest_fs_migration_version}")

            # If DB is fresh (version 0) and there are migrations, stamp it to the latest FS version
            if current_db_version == 0 and latest_fs_migration_version > 0:
                self.logger.info(f"Fresh database detected. Stamping migration version to {latest_fs_migration_version}.")
                migration.set_version(latest_fs_migration_version)
                current_db_version = latest_fs_migration_version # Update current_db_version for subsequent logic
                self.logger.info(f"Database version after stamping: {current_db_version}")
            
            self.logger.debug(f"Found {len(migration_files)} migration files:")
            for mf in migration_files:
                self.logger.debug(f"  - {mf.name}")
            
            # Do a version check and create a list of applicable migrations
            applicable_migrations = []
            for migration_file in migration_files:
                self.logger.debug(f"Running pre-checks for migration files: {migration_file.name}")
                try:
                    version = int(migration_file.stem.split('_')[0])
                except ValueError:
                    self.logger.warning(f"Skipping {migration_file.name} - invalid version format")
                    continue
                    
                self.logger.debug(f"Migration file version: {version}, current DB version: {current_db_version}")
                
                if version > current_db_version:
                    applicable_migrations.append(migration_file)

            self.logger.debug(f"Found {len(applicable_migrations)} applicable migrations to run")
            if len(applicable_migrations) > 0:
                if self.backup_on_upgrade:
                    self.logger.info("Database backup before migrations is enabled.")
                    self.logger.info("Attempting to backup database before migrations as per settings...")
                    self.backup_service.backup_db(db_path_str=self.db_path, name=f"old", system_backup=True)
                else:
                    self.logger.debug("Skipping database backup before migrations as per settings.")
            else:
                self.logger.debug("No migrations to run, skipping migration process.")
                return

            # Run each migration file
            for migration_file in applicable_migrations:
                self.logger.debug(f"Processing migration file: {migration_file.name}")
                
                self.logger.info(f"Applying migration {migration_file.name}")
                
                # Import and run migration
                spec = importlib.util.spec_from_file_location(
                    f"migration_{version}", 
                    migration_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Execute migration in a transaction
                with database.atomic():
                    try:
                        database.execute_sql('PRAGMA foreign_keys=OFF;')
                        self.logger.debug(f"Starting migration {version}")
                        module.upgrade(migration.migrator)
                        self.logger.debug(f"Migration {version} code executed successfully")
                        
                        # Update the version in migrations table
                        migration.set_version(version)
                        self.logger.debug(f"Migration {version} version recorded")
                        database.execute_sql('PRAGMA foreign_keys=ON;')
                        
                        self.logger.info(f"Successfully applied migration {version}")
                    except Exception as e:
                        self.logger.error(f"Failed to apply migration {version}: {e}")
                        database.execute_sql('PRAGMA foreign_keys=ON;')
                        raise
                            
            self.logger.info("Database migrations complete")
            
        except Exception as e:
            self.logger.error(f"Error running migrations: {e}")
            raise

    def _add_default_tasks(self):
        # Add default search if it doesn't exist
        self.add_search(
            prompt=SettingsService._DEFAULT_PROMPT_TEMPLATE, # Use _DEFAULT_PROMPT_TEMPLATE
            name="recently_watched",
            id=1)
        
        # Add default recently watched search schedule if it doesn't exist
        job_id="recently_watched"
        schedule = self.get_schedule_by_job_id(job_id)
        if not schedule:
            self.add_schedule(
                search_id=1,
                job_id=job_id,
                func_name="process_watch_history",
                year="*",
                month="*",
                hour="0",
                minute="0",
                day="*",
                day_of_week="sun",
                args=[],
                kwargs={},
                enabled=False)
            
        # Add daily job for syncing watch history if it doesn't exist
        job_id="sync_watch_history"
        schedule = self.get_schedule_by_job_id(job_id)
        if not schedule:
            self.add_schedule(
                search_id=None,
                job_id=job_id,
                func_name="sync_watch_history",
                year="*",
                month="*",
                hour="3",
                minute="0",
                day="*",
                day_of_week="*",
                args=[],
                kwargs={},
                enabled=True)

    def create_media(self, media_data: Dict[str, Any]) -> Optional[int]:
        """Create a new media entry in the database."""
        try:
            # Convert search_id to Search instance if provided
            if 'search_id' in media_data:
                search_id = media_data.pop('search_id')
                if search_id:
                    media_data['search'] = Search.get_by_id(search_id)

            media = Media.create(**media_data)
            return media.id
        except Exception as e:
            self.logger.error(f"Error creating media entry: {e}")
            return None

    def read_media(self, media_id: int) -> Optional[Dict[str, Any]]:
        """Read a media entry from the database."""
        try:
            media = Media.get_by_id(media_id)
            return model_to_dict(media)
        except Media.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error reading media entry: {e}")
            return None

    def update_media(self, media_id: int, media_data: Dict[str, Any]) -> bool:
        """Update a media entry in the database."""
        try:
            media_data['updated_at'] = datetime.now()
            query = Media.update(media_data).where(Media.id == media_id)
            return query.execute() > 0
        except Exception as e:
            self.logger.error(f"Error updating media entry: {e}")
            return False

    def delete_media(self, media_id: int) -> bool:
        """Delete a media entry from the database."""
        try:
            return Media.delete().where(Media.id == media_id).execute() > 0
        except Exception as e:
            self.logger.error(f"Error deleting media entry: {e}")
            return False

    def delete_media_by_tmdb_id(self, tmdb_id: str, media_type: str) -> bool:
        """Delete a media entry from the database by TMDB ID and media type."""
        try:
            query = Media.delete().where(
                (Media.tmdb_id == tmdb_id) & (Media.media_type == media_type)
            )
            return query.execute() > 0
        except Exception as e:
            self.logger.error(f"Error deleting media entry by TMDB ID {tmdb_id}: {e}")
            return False

    def add_watch_history(self, title: str, id: str, media_type: str, watched_by: str, last_played_date: str, poster_url: Optional[str] = None, poster_url_source: Optional[str] = None) -> bool:
        """
        Add or update a watch history entry.
        Assumes WatchHistory model has fields for media_jellyfin_id and media_type.

        Args:
            title (str): The title of the media.
            media_jellyfin_id (str): The Jellyfin ID of the media.
            media_type (str): The type of media (e.g., 'movie', 'tv').
            watched_by (str): The identifier of who watched the media.
            last_played_date_str (str): The ISO 8601 string of the last played date.
            poster_url (Optional[str]): URL of the poster image.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        try:
            # If last_played_date is None, default to now (UTC)
            if last_played_date is None:
                self.logger.info(f"last_played_date is None for '{title}', defaulting to current UTC time.")
                last_played_date = datetime.now(timezone.utc).isoformat()
                
            dt_last_played_date: datetime
            try:
                # Parse the ISO 8601 date string.
                # Jellyfin's LastPlayedDate is typically UTC and may end with 'Z'.
                if last_played_date.endswith('Z'):
                    # Python's fromisoformat before 3.11 doesn't handle 'Z' directly.
                    dt_last_played_date = datetime.fromisoformat(last_played_date[:-1] + '+00:00')
                else:
                    # Attempt direct parsing for other ISO 8601 compliant strings (e.g., with offset)
                    dt_last_played_date = datetime.fromisoformat(last_played_date)
            except ValueError as ve:
                self.logger.error(f"Error parsing last_played_date '{last_played_date}' for '{title}': {ve}")
                return False
            
            # Convert to naive UTC datetime for storage, common practice for SQLite with Peewee.
            # This assumes your `watched_at` field in Peewee stores naive datetimes representing UTC.
            dt_last_played_date_utc = dt_last_played_date.astimezone(timezone.utc).replace(tzinfo=None)
            
            # Check if an entry already exists for this media_jellyfin_id and user.
            # This requires WatchHistory model to have 'media_jellyfin_id' and 'media_type' fields.
            existing_entry = WatchHistory.get_or_none(
                (fn.Lower(WatchHistory.title) == title.lower()) &
                (fn.Lower(WatchHistory.watched_by) == watched_by.lower())
            )

            if existing_entry:
                existing_entry.last_played_date = dt_last_played_date_utc
                existing_entry.media_type = media_type # Update type
                existing_entry.media_id = id # This is either the TMDB or JellyfinID
                existing_entry.updated_at = datetime.now()
                existing_entry.poster_url = poster_url
                existing_entry.poster_url_source = poster_url_source
                existing_entry.save()
                self.logger.info(f"Successfully updated watch history for '{title}' (ID: {id}) by {watched_by}")
            else:
                WatchHistory.create(
                    title=title,
                    media_id=id,
                    media_type=media_type,
                    watched_by=watched_by,
                    last_played_date=dt_last_played_date_utc,
                    poster_url=poster_url,
                    poster_url_source=poster_url_source,
                )
                self.logger.info(f"Successfully added new watch history for '{title}' (ID: {id}) by {watched_by}")
            return True
        except Exception as e:
            self.logger.error(f"Error processing watch history for title '{title}' (ID: {id}): {e}", exc_info=True)
            return False
        
    def update_watch_history_processed(self, watch_history_id: int, processed: bool) -> bool:
        """
        Update the processed status and processed_at timestamp for a watch history entry.

        Args:
            watch_history_id (int): The primary key of the WatchHistory entry.
            processed (bool): The new processed status.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        try:
            history_entry = WatchHistory.get_by_id(watch_history_id)
            history_entry.processed = processed
            if processed:
                history_entry.processed_at = datetime.now()
            else:
                history_entry.processed_at = None
            history_entry.updated_at = datetime.now()  # Also update the general updated_at timestamp
            history_entry.save()
            self.logger.info(f"Successfully updated processed status for watch history ID {watch_history_id} to {processed}.")
            return True
        except WatchHistory.DoesNotExist:
            self.logger.warning(f"Watch history entry with ID {watch_history_id} not found for updating processed status.")
            return False
        except Exception as e:
            self.logger.error(f"Error updating processed status for watch history ID {watch_history_id}: {e}", exc_info=True)
            return False
        
    def get_watch_history_by_title(self, title: str, watched_by: Optional[str] = None) -> Optional[WatchHistory]:
        """Get the most recent watch history entry for a specific title and user.

        Args:
            title (str): The title of the media.
            watched_by (str): The identifier of who watched the media.

        Returns:
            Optional[WatchHistory]: The WatchHistory object if found, otherwise None.
        """
        try:
            if watched_by:
                wh = WatchHistory.select().where(
                (WatchHistory.title == title) & (WatchHistory.watched_by == watched_by)
            )
            else:
                wh = WatchHistory.select().where(WatchHistory.title == title)
            return wh.order_by(WatchHistory.watched_at.desc()).get_or_none()
        except Exception as e:
            self.logger.error(f"Error retrieving watch history for title '{title}' by {watched_by}: {e}")
            return None

    def get_watch_history_for_title(self, title: str, watched_by: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the most recent watch history entry for a specific title, optionally filtered by user.

        Args:
            title (str): The title of the media.
            watched_by (Optional[str]): The identifier of who watched the media. If None, history for all users is returned.

        Returns:
            Optional[Dict[str, Any]]: A dictionary representing the most recent watch history entry, or None if not found.
        """
        try:
            query = WatchHistory.select().where(WatchHistory.title == title)

            if watched_by:
                query = query.where(WatchHistory.watched_by == watched_by)

            # Get the most recent entry
            history_entry = query.order_by(WatchHistory.last_played_date.desc()).get_or_none()

            return model_to_dict(history_entry) if history_entry else None
        except Exception as e:
            self.logger.error(f"Error retrieving watch history for title '{title}' (user: {watched_by}): {e}")
            return None
        
    def get_watch_history_item_by_id(self, history_item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific watch history item by its ID.

        Args:
            history_item_id (int): The ID of the watch history item.

        Returns:
            Optional[Dict[str, Any]]: A dictionary representing the watch history item, or None if not found.
        """
        try:
            history_item = WatchHistory.get_by_id(history_item_id)
            return model_to_dict(history_item)
        except WatchHistory.DoesNotExist:
            return None

    def get_watch_history(self, limit: Optional[int] = 10, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, processed: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Get watch history, optionally filtered by date range.
        
        Args:
            limit (Optional[int]): Maximum number of records to return. If None, returns all.
            start_date (Optional[datetime]): The start date for filtering.
            end_date (Optional[datetime]): The end date for filtering.

        Returns:
            List[Dict[str, Any]]: A list of watch history entries.
        """
        try:
            query = (WatchHistory
                    .select(WatchHistory)
                    .order_by(WatchHistory.last_played_date.desc()))
            
            if start_date:
                query = query.where(WatchHistory.last_played_date >= start_date)
            if end_date:
                query = query.where(WatchHistory.last_played_date <= end_date)
            if processed is not None:
                query = query.where(WatchHistory.processed == processed)
            if limit is not None:
                query = query.limit(limit)
            return [model_to_dict(h) for h in query]
        except Exception as e:
            self.logger.error(f"Error retrieving watch history: {e}")
            return []

    def delete_watch_history_item(self, history_item_id: int) -> bool:
        """
        Deletes a specific watch history item by its primary key ID.

        Args:
            history_item_id (int): The ID of the watch history item to delete.

        Returns:
            bool: True if the item was deleted, False otherwise (e.g., not found or error).
        """
        try:
            query = WatchHistory.delete().where(WatchHistory.id == history_item_id)
            return query.execute() > 0  # Returns the number of rows deleted
        except Exception as e:
            self.logger.error(f"Error deleting watch history item with ID {history_item_id}: {e}", exc_info=True)
            return False

    def delete_all_watch_history(self) -> int:
        """
        Deletes all watch history items from the database.

        Returns:
            int: The number of rows deleted. Returns 0 on error.
        """
        try:
            query = WatchHistory.delete()
            return query.execute()  # Returns the number of rows deleted
        except Exception as e:
            self.logger.error(f"Error deleting all watch history items: {e}", exc_info=True)
            return 0

    def get_unique_media_values_by_field(self, field_name: str) -> List[Any]:
        """
        Get unique values from a specific field in the Media table.
        If the field contains comma-delimited strings, they will be split.

        Args:
            field_name (str): The name of the column/field in Media to get unique values from.

        Returns:
            List[Any]: A list of unique values from the specified field.
        """
        try:
            if not hasattr(Media, field_name):
                self.logger.error(f"Invalid field_name '{field_name}' for Media table.")
                return []

            query = Media.select(getattr(Media, field_name)).where(getattr(Media, field_name).is_null(False))
            
            all_individual_values = set()

            for item_row in query:
                raw_value = getattr(item_row, field_name)
                
                if isinstance(raw_value, str):
                    # Split comma-delimited string and add individual parts
                    # Ensure parts are stripped of whitespace and non-empty
                    parts = [part.strip() for part in raw_value.split(',') if part.strip()]
                    for part in parts:
                        all_individual_values.add(part)
                elif raw_value is not None: # For non-string, non-null values
                    all_individual_values.add(raw_value)
            
            return sorted(list(all_individual_values)) # Sorted for consistent output
        except Exception as e:
            self.logger.error(f"Error retrieving unique media values for field '{field_name}': {e}")
            return []

    def search_media(self, query: str) -> List[Dict[str, Any]]:
        """Search for media entries by title."""
        try:
            media = (Media
                    .select()
                    .where(Media.title.contains(query))
                    .order_by(Media.title))
            return [model_to_dict(m) for m in media]
        except Exception as e:
            self.logger.error(f"Error searching media: {e}")
            return []

    def add_search_stat(self, search_id: int, token_counts: Dict[str, int]) -> Optional[int]:
        """Add a search stats entry."""
        try:
            stat = SearchStat.create(
                search_id=search_id,
                prompt_token_count=token_counts.get('prompt_token_count') or 0,
                candidates_token_count=token_counts.get('candidates_token_count') or 0,
                thoughts_token_count=token_counts.get('thoughts_token_count') or 0,
                total_token_count=token_counts.get('total_token_count') or 0
            )
            return stat.id
        except Exception as e:
            self.logger.error(f"Error adding search stats: {e}")
            return None

    def get_search_stats(self, search_id: Optional[int] = 0, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get search stats, either for a specific search or all searches."""
        try:
            query = (SearchStat
                    .select()
                    .order_by(SearchStat.created_at.desc()))
            
            return [model_to_dict(stat) for stat in query]
        except Exception as e:
            self.logger.error(f"Error getting search stats: {e}")
            return []

    def toggle_ignore(self, media_id: int) -> bool:
        """Toggle the ignore status for a media entry."""
        try:
            media = Media.get_by_id(media_id)
            media.ignore = not media.ignore
            media.updated_at = datetime.now()
            return media.save() > 0
        except Exception as e:
            self.logger.error(f"Error toggling ignore status: {e}")
            return False

    def get_non_ignored_media(self) -> List[Dict[str, Any]]:
        """Get all media entries that are not ignored."""
        try:
            media = (Media
                    .select()
                    .where(Media.ignore == False)
                    .order_by(Media.created_at.desc()))
            return [model_to_dict(m) for m in media]
        except Exception as e:
            self.logger.error(f"Error retrieving non-ignored media: {e}")
            return []

    def get_ignored_media(self) -> List[Dict[str, Any]]:
        """Get all media entries that are ignored."""
        try:
            media = (Media
                    .select()
                    .where(Media.ignore == True)
                    .order_by(Media.title))
            return [model_to_dict(m) for m in media]
        except Exception as e:
            self.logger.error(f"Error retrieving ignored media: {e}")
            return []

    def get_ignored_media_titles(self) -> List[str]:
        """Get all distinct titles of ignored media entries."""
        try:
            query = (Media
                    .select(Media.title)
                    .where(Media.ignore == True)
                    .order_by(Media.title)
                    .distinct())
            return [m.title for m in query]
        except Exception as e:
            self.logger.error(f"Error retrieving ignored media titles: {e}")
            return []

    def update_ignore_status(self, media_id: int, ignore: bool) -> bool:
        """Update the ignore status for a media entry."""
        try:
            return (Media
                    .update(ignore=ignore, updated_at=datetime.now())
                    .where(Media.id == media_id)
                    .execute() > 0)
        except Exception as e:
            self.logger.error(f"Error updating ignore status: {e}")
            return False

    def add_search(self, prompt: str, name: str = None, id: Optional[int] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Add a new search prompt."""
        try: 
            # Allow inserting a search with an ID, useful for migrations or specific cases
            if id is not None:
                search = Search.get_or_none(Search.id == id)
                if not search:
                    search = Search.create(id=id, prompt=prompt, name=name, kwargs=json.dumps(kwargs.get('kwargs')))
                else:
                    self.logger.debug(f"Skipping search add, one already exists with ID {id}")
            else:
                search = Search.create(prompt=prompt, name=name, kwargs=json.dumps(kwargs.get('kwargs')))
            return model_to_dict(search)
        except Exception as e:
            self.logger.error(f"Error adding search: {e}")
            return None

    def update_search(self, search_id: int, prompt: str, name: str = None, **kwargs) -> bool:
        """Update an existing search prompt."""
        try:
            update_data = {'prompt': prompt}
            if name is not None:
                update_data['name'] = name

            if kwargs:
                update_data['kwargs'] = json.dumps(kwargs.get('kwargs'))

            return Search.update(**update_data).where(Search.id == search_id).execute() > 0
        except Exception as e:
            self.logger.error(f"Error updating search: {e}")
            return False

    def update_search_run_date(self, search_id: int, last_run_date: datetime) -> bool:
        """Update the last_run_date for a specific search entry."""
        try:
            query = Search.update(last_run_date=last_run_date).where(Search.id == search_id)
            updated_rows = query.execute()
            if updated_rows > 0:
                self.logger.info(f"Successfully updated last_run_date for search ID {search_id} to {last_run_date}")
                return True
            else:
                self.logger.warning(f"No search found with ID {search_id} to update last_run_date.")
                return False
        except Exception as e:
            self.logger.error(f"Error updating last_run_date for search ID {search_id}: {e}")
            return False


    def get_searches(self, limit: Optional[int] = 10) -> List[Dict[str, Any]]:
        """Get recent searches, including their associated schedule information if available."""
        try:
            # Select fields from Search and all fields from Schedule
            query = (Search
                     .select(Search, Schedule)  # Select all fields from both models
                     .join(Schedule, 
                           join_type=JOIN.LEFT_OUTER,
                           on=(Search.id == Schedule.search_id))
                      .order_by(Search.created_at.desc()))
            
            if limit is not None:
                query = query.limit(limit)

            self.logger.debug(f"Executing query to get searches with schedules: {query.sql()}")
            
            results = []
            for search_instance in query:
                search_dict = model_to_dict(search_instance, recurse=False)
                self.logger.debug(f"search_instance: {search_instance}")
                if hasattr(search_instance, 'schedule') and search_instance.schedule.id is not None: # Check if schedule.id is not None to ensure it's a real schedule
                    schedule_dict = model_to_dict(search_instance.schedule, recurse=False)
                    search_dict["schedule"] = schedule_dict
                results.append(search_dict) 
            return results
        except Exception as e:
            self.logger.error(f"Error retrieving searches with schedules: {e}", exc_info=True)
            return []

    def get_search(self, search_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific search by ID."""
        try:
            search = Search.get_by_id(search_id)
            return model_to_dict(search)
        except Search.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting search: {e}")
            return None

    def get_search_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific search by name."""
        try:
            search = Search.get(Search.name == name)
            return model_to_dict(search)
        except Search.DoesNotExist:
            self.logger.info(f"Search with name '{name}' not found.")
            return None
        except Exception as e:
            self.logger.error(f"Error getting search by name '{name}': {e}")
            return None

    def delete_search(self, search_id: int) -> bool:
        """Delete a search entry."""
        try:
            return Search.delete().where(Search.id == search_id).execute() > 0
        except Exception as e:
            self.logger.error(f"Error deleting search: {e}")
            return False

    def clear_searches(self) -> bool:
        """Clear all search entries."""
        try:
            Search.delete().execute()
            return True
        except Exception as e:
            self.logger.error(f"Error clearing searches: {e}")
            return False

    def add_schedule(self, job_id: str, func_name: str, search_id: Optional[int] = None, **kwargs) -> Optional[int]:
        """Add a new schedule entry."""
        try:
            schedule_data = {
                'search_id': search_id,
                'job_id': job_id,
                'func_name': func_name,
                'year': kwargs.get('year'),
                'month': kwargs.get('month'),
                'hour': kwargs.get('hour'),
                'minute': kwargs.get('minute'),
                'day': kwargs.get('day'),
                'day_of_week': kwargs.get('day_of_week'),
                'args': json.dumps(kwargs.get('args')),
                'kwargs': json.dumps(kwargs.get('kwargs')),
                'enabled': kwargs.get('enabled', True)
            }
            schedule = Schedule.create(**schedule_data)
            return schedule.id
        except Exception as e:
            self.logger.error(f"Error adding schedule: {e}")
            return None

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules."""
        try:
            schedules = Schedule.select()
            return [model_to_dict(s) for s in schedules]
        except Exception as e:
            self.logger.error(f"Error getting schedules: {e}")
            return []

    def update_schedule(self, search_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Update specific fields of an existing schedule identified by job_id.

        Args:
            search_id (int): The unique identifier of the schedule to update.
            update_data (Dict[str, Any]): A dictionary containing the fields to update.
                Allowed keys: 'search_id', 'func_name', 'year', 'month', 
                              'day_of_week', 'hour', 'minute', 'args', 
                              'kwargs', 'enabled'.

        Returns:
            bool: True if the update was successful and at least one row was affected, False otherwise.
        """
        if not update_data:
            self.logger.info(f"No data provided to update schedule with search_id '{search_id}'.")
            return False # No update performed

        payload = {}
        valid_direct_fields = [
            'year', 'month', 'day', 'day_of_week', 'hour', 'minute', 'enabled'
        ]

        for field in valid_direct_fields:
            if field in update_data:
                payload[field] = update_data[field]

        if not payload:
            self.logger.info(f"No valid fields provided in update_data for schedule '{search_id}'.")
            return False

        payload['updated_at'] = datetime.now()

        try:
            affected_rows = Schedule.update(**payload).where(Schedule.search_id == search_id).execute()
            if affected_rows > 0:
                self.logger.info(f"Successfully updated schedule with search_id '{search_id}'.")
                return True
            self.logger.info(f"Schedule with search_id '{search_id}' not found or no changes made by update.")
            return False
        except Exception as e:
            self.logger.error(f"Error updating schedule with search_id '{search_id}': {e}", exc_info=True)
            return False

    def delete_schedule(self, job_id: str) -> bool:
        """Delete a schedule."""
        try:
            return Schedule.delete().where(Schedule.job_id == job_id).execute() > 0
        except Exception as e:
            self.logger.error(f"Error deleting schedule: {e}")
            return False
        
    def delete_schedule_by_search_id(self, search_id: int) -> bool:
        """Delete a schedule."""
        try:
            return Schedule.delete().where(Schedule.search_id == search_id).execute() > 0
        except Schedule.DoesNotExist:
            self.logger.info(f"Schedule with search_id '{search_id}' not found.")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting schedule: {e}")
            return False

    def get_schedule_by_search_id(self, search_id: int) -> Optional[Dict[str, Any]]:
        """Get a schedule for a specific search."""
        try:
            schedule = Schedule.get(Schedule.search_id == search_id)
            return model_to_dict(schedule)
        except Schedule.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting schedule: {e}")
            return None

    def get_schedule_by_job_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a schedule by its job_id."""
        try:
            schedule = Schedule.get(Schedule.job_id == job_id)
            return model_to_dict(schedule)
        except Schedule.DoesNotExist:
            self.logger.info(f"Schedule with job_id '{job_id}' not found.")
            return None
        except Exception as e:
            self.logger.error(f"Error getting schedule by job_id '{job_id}': {e}")
            return None

    def list_schedules(self) -> List[Dict[str, Any]]:
        """Get all enabled schedules with their search queries."""
        try:
            query = (Schedule
                    .select(Schedule, Search.query)
                    .join(Search)
                    .where(Schedule.enabled == True))
            return [model_to_dict(s, recurse=True) for s in query]
        except Exception as e:
            self.logger.error(f"Error listing schedules: {e}")
            return []

    def get_setting(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a setting by name."""
        try:
            setting = Settings.get(Settings.name == name)
            return model_to_dict(setting)
        except Settings.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting setting: {e}")
            return None

    def get_settings_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get all settings in a group."""
        try:
            settings = Settings.select().where(Settings.group == group)
            return [model_to_dict(s) for s in settings]
        except Exception as e:
            self.logger.error(f"Error getting settings for group {group}: {e}")
            return []

    def get_all_settings(self) -> List[Dict[str, Any]]:
        """Get all settings."""
        try:
            settings = Settings.select()
            return [model_to_dict(s) for s in settings]
        except Exception as e:
            self.logger.error(f"Error getting all settings: {e}")
            return []

    def upsert_setting(self, name: str, value: str, group: str, default: Optional[str] = None, description: Optional[str] = None) -> bool:
        """Create or update a setting."""
        try:
            setting, created = Settings.get_or_create(
                name=name,
                defaults={
                    'group': group,
                    'value': value,
                    'default': default,
                    'description': description
                }
            )
            
            if not created:
                setting.value = value
                setting.group = group
                setting.default = default if default is not None else setting.default
                setting.description = description if description is not None else setting.description
                setting.updated_at = datetime.now()
                setting.save()
            
            return True
        except Exception as e:
            self.logger.error(f"Error upserting setting: {e}")
            return False

    def delete_setting(self, name: str) -> bool:
        """Delete a setting by name."""
        try:
            return Settings.delete().where(Settings.name == name).execute() > 0
        except Exception as e:
            self.logger.error(f"Error deleting setting: {e}")
            return False

    def cleanup(self):
        """Close the database connection."""
        if not database.is_closed():
            database.close()
            self.logger.debug("Closed database connection")

    def __del__(self):
        """Cleanup when the object is destroyed."""
        self.cleanup()

# def model_to_dict(model, recurse: bool = False) -> dict:
#     """Convert a model instance to a dictionary."""
#     data = model.__data__.copy()
#     if recurse:
#         for field in model._meta.backrefs:
#             data[field.backref] = [model_to_dict(rel_obj) for rel_obj in getattr(model, field.backref)]
#     return data
