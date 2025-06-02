import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

class BackupService:
    """
    Handles database backup and restore operations.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def backup_db(self, db_path_str: str, name: str, system_backup: Optional[bool] = False) -> Optional[str]:
        """
        Creates a timestamped backup of the SQLite database file.

        Args:
            db_path_str (str): The path to the database file.

        Returns:
            Optional[str]: The path to the created backup file, or None if backup failed.
        """
        db_file_path = Path(db_path_str)
        if not db_file_path.exists():
            self.logger.info(f"Database file {db_file_path} does not exist. Skipping backup.")
            return None

        backup_dir = Path("/backups")
        backup_dir.mkdir(exist_ok=True)  # Ensure backup directory exists

        if system_backup:
            backup_file_name = f"{db_file_path.stem}_backup_{name}{db_file_path.suffix}"
        else:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            backup_file_name = f"{db_file_path.stem}_backup_{name}_{timestamp}{db_file_path.suffix}"
        backup_path = backup_dir / backup_file_name

        try:
            shutil.copy2(db_file_path, backup_path)
            self.logger.info(f"Successfully backed up database to {backup_path}")
            return str(backup_path)
        except Exception as e:
            self.logger.error(f"Failed to backup database from {db_file_path} to {backup_path}: {e}")
            return None

    def restore_db(self, backup_path_str: str, db_path_str: str) -> bool:
        """
        Restores the database from a backup file.

        Args:
            backup_path_str (str): The path to the backup file.
            db_path_str (str): The path where the database should be restored.

        Returns:
            bool: True if restoration was successful, False otherwise.
        """
        backup_path = Path(backup_path_str)
        db_path = Path(db_path_str)

        if not backup_path.exists():
            self.logger.error(f"Backup file {backup_path} does not exist. Cannot restore.")
            return False

        try:
            # Ensure the parent directory of the db_path exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, db_path)
            self.logger.info(f"Successfully restored database from {backup_path} to {db_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore database from {backup_path} to {db_path}: {e}")
            return False