import sqlite3
import os
import gzip
import shutil
import datetime
from config.config import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, "instance/test_platform.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DAILY_BACKUP_RETENTION = 3  # Keep last 3 daily backups
WEEKLY_BACKUP_RETENTION = 4  # Keep last 4 weekly backups (30 days)

def perform_backup(logger):
    logger.info("Starting backup process.")
    # Connect to the database
    con = sqlite3.connect(DB_PATH)

    try:
        # Run integrity check
        cursor = con.cursor()
        result = cursor.execute('PRAGMA integrity_check;').fetchall()

        if result[0][0] != 'ok':
            logger.error('Database integrity check failed: %s', result)
            print('Database integrity check failed:', result)
            return

        # Perform the backup
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        backup_filename = f'database_backup_{timestamp}.db'
        backup_filepath = os.path.join(BACKUP_DIR, backup_filename)

        # Use SQLite's backup API
        backup_con = sqlite3.connect(backup_filepath)
        with backup_con:
            con.backup(backup_con)
        backup_con.close()

        # Compress the backup
        compressed_backup_filepath = f'{backup_filepath}.gz'
        with open(backup_filepath, 'rb') as f_in:
            with gzip.open(compressed_backup_filepath, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove the uncompressed backup file
        os.remove(backup_filepath)

        logger.info('Backup completed successfully: %s', compressed_backup_filepath)
        print('Backup completed successfully:', compressed_backup_filepath)

    except sqlite3.Error as e:
        logger.error('SQLite error during backup: %s', e)
        print('SQLite error:', e)

    finally:
        # Close the connection
        con.close()

def cleanup_old_backups(logger):
    logger.info("Starting cleanup of old backups.")
    # Get current date
    now = datetime.datetime.now()

    # List all backup files
    backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith('database_backup_')]

    # Sort by modification time
    backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)))

    # Separate daily and weekly backups
    daily_backups = []
    weekly_backups = []

    for backup_file in backup_files:
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(backup_path))
        age_in_days = (now - modification_time).days

        if age_in_days <= 3:
            daily_backups.append(backup_file)
        elif age_in_days <= 30:
            weekly_backups.append(backup_file)

    # Retain the latest 3 daily backups and 4 weekly backups
    daily_backups_to_delete = daily_backups[:-DAILY_BACKUP_RETENTION]
    weekly_backups_to_delete = weekly_backups[:-WEEKLY_BACKUP_RETENTION]

    # Delete old backups
    for backup_file in daily_backups_to_delete + weekly_backups_to_delete:
        os.remove(os.path.join(BACKUP_DIR, backup_file))
        logger.info('Deleted old backup: %s', backup_file)
        print('Deleted old backup:', backup_file)

    logger.info("Cleanup of old backups completed.")

