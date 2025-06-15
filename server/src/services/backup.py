import logging
import shutil
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

class BackupService:
    """
    Handles database backup and restore operations.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, db_type: str = "sqlite", db_config: Optional[Dict] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.db_type = db_type
        self.db_config = db_config if db_config else {}

    def backup_db(self, name: str, db_path_str: Optional[str] = None, system_backup: Optional[bool] = False) -> Optional[str]:
        """
        Creates a backup of the database.

        Args:
            db_path_str (Optional[str]): The path to the SQLite database file. Required if db_type is 'sqlite'.
            name (str): A name component for the backup file.
            system_backup (Optional[bool]): If True, uses a simpler backup name format.

        Returns:
            Optional[str]: The path to the created backup file, or None if backup failed.
        """
        backup_dir = Path("/backups")
        backup_dir.mkdir(exist_ok=True)  # Ensure backup directory exists

        timestamp_part = datetime.now().strftime('%Y%m%d%H%M%S')
        base_name = "discovarr_db" # Generic base name for PostgreSQL or if SQLite path is complex

        if system_backup:
            backup_file_name_stem = f"{base_name}_backup_{name}"
        else:
            backup_file_name_stem = f"{base_name}_backup_{name}_{timestamp_part}"

        if self.db_type == "sqlite":
            if not db_path_str:
                self.logger.error("SQLite backup requested but db_path_str is not provided.")
                return None
            db_file_path = Path(db_path_str)
            if not db_file_path.exists():
                self.logger.info(f"SQLite database file {db_file_path} does not exist. Skipping backup.")
                return None
            
            # Use SQLite file stem for more specific backup name if desired, or keep generic
            # backup_file_name_stem = f"{db_file_path.stem}_backup_{name}_{timestamp_part}" # Alternative
            backup_file_name = f"{backup_file_name_stem}{db_file_path.suffix}"
            backup_path = backup_dir / backup_file_name
            try:
                shutil.copy2(db_file_path, backup_path)
                self.logger.info(f"Successfully backed up SQLite database to {backup_path}")
                return str(backup_path)
            except Exception as e:
                self.logger.error(f"Failed to backup SQLite database from {db_file_path} to {backup_path}: {e}")
                return None
        elif self.db_type == "postgres":
            backup_file_name = f"{backup_file_name_stem}.sql" # pg_dump typically outputs .sql or .dump
            backup_path = backup_dir / backup_file_name
            
            pg_dump_cmd = [
                "pg_dump",
                "-h", self.db_config.get("host", "localhost"),
                "-p", str(self.db_config.get("port", 5432)),
                "-U", self.db_config.get("user"),
                "-d", self.db_config.get("dbname"),
                "-f", str(backup_path),
                "--no-password" # Assuming PGPASSWORD env var or .pgpass is used
            ]
            env = os.environ.copy()
            if self.db_config.get("password"):
                 env["PGPASSWORD"] = self.db_config.get("password")

            self.logger.info(f"Attempting PostgreSQL backup using pg_dump to {backup_path}")
            self.logger.debug(f"pg_dump command (password omitted for logging): {' '.join([p if i != pg_dump_cmd.index('-U') + 1 and i != pg_dump_cmd.index('-p') +1 else '***' if p == self.db_config.get('password') else p for i, p in enumerate(pg_dump_cmd) if pg_dump_cmd[i-1] != '-U' or pg_dump_cmd[i-1] != '-p' or p != self.db_config.get('password')])}")

            try:
                if not shutil.which("pg_dump"):
                    self.logger.error("pg_dump command not found. Cannot backup PostgreSQL. Ensure client tools are installed and in PATH.")
                    return None
                process = subprocess.run(pg_dump_cmd, env=env, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    self.logger.info(f"Successfully backed up PostgreSQL database to {backup_path}")
                    return str(backup_path)
                else:
                    self.logger.error(f"pg_dump failed with exit code {process.returncode}:\nSTDOUT: {process.stdout}\nSTDERR: {process.stderr}")
                    if backup_path.exists(): backup_path.unlink(missing_ok=True)
                    return None
            except FileNotFoundError:
                 self.logger.error("pg_dump command not found. Ensure PostgreSQL client tools are installed and in PATH.")
                 return None
            except Exception as e:
                self.logger.error(f"Failed to backup PostgreSQL database: {e}")
                if backup_path.exists(): backup_path.unlink(missing_ok=True)
                return None
        else:
            self.logger.warning(f"Unsupported database type '{self.db_type}' for backup.")
            return None

    def restore_db(self, backup_path_str: str, db_path_str: Optional[str] = None) -> bool:
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

        if self.db_type == "sqlite":
            if not db_path:
                self.logger.error("SQLite restore requested but db_path_str is not provided.")
                return False
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, db_path)
                self.logger.info(f"Successfully restored SQLite database from {backup_path} to {db_path}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to restore SQLite database from {backup_path} to {db_path}: {e}")
                return False
        elif self.db_type == "postgres":
            psql_cmd = [
                "psql",
                "-h", self.db_config.get("host", "localhost"),
                "-p", str(self.db_config.get("port", 5432)),
                "-U", self.db_config.get("user"),
                "-d", self.db_config.get("dbname"),
                "-f", str(backup_path),
                "--no-password"
            ]
            env = os.environ.copy()
            if self.db_config.get("password"):
                 env["PGPASSWORD"] = self.db_config.get("password")

            self.logger.info(f"Attempting PostgreSQL restore using psql from {backup_path} to database {self.db_config.get('dbname')}")
            # Similar logging for psql_cmd as for pg_dump_cmd if desired
            try:
                if not shutil.which("psql"):
                    self.logger.error("psql command not found. Cannot restore PostgreSQL. Ensure client tools are installed and in PATH.")
                    return False
                process = subprocess.run(psql_cmd, env=env, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    self.logger.info(f"Successfully restored PostgreSQL database from {backup_path}")
                    return True
                else:
                    self.logger.error(f"psql restore failed with exit code {process.returncode}:\nSTDOUT: {process.stdout}\nSTDERR: {process.stderr}")
                    return False
            except FileNotFoundError:
                 self.logger.error("psql command not found. Ensure PostgreSQL client tools are installed and in PATH.")
                 return False
            except Exception as e:
                self.logger.error(f"Failed to restore PostgreSQL database: {e}")
                return False
        else:
            self.logger.warning(f"Unsupported database type '{self.db_type}' for restore.")
            return False