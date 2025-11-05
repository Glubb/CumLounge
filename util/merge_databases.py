#!/usr/bin/env python3
"""
Merge multiple SecretLounge databases into a single unified database.

This script imports users, message mappings, and bot_users data from source
databases into a target database. It handles the bot_id scoping introduced
for multi-instance support.

Usage:
    python util/merge_databases.py <target_db> <source_db> <bot_id> [--dry-run]

Arguments:
    target_db   - Path to the target SQLite database (will be created if missing)
    source_db   - Path to the source SQLite database to import from
    bot_id      - Bot ID to assign to imported message mappings and bot_users

Options:
    --dry-run   - Show what would be imported without making changes
    --skip-users - Skip importing users (only import message mappings/bot_users)
    --skip-mappings - Skip importing message mappings
    --skip-bot-users - Skip importing bot_users table

Examples:
    # Import from old instance with bot_id 123456
    python util/merge_databases.py secretlounge.sqlite old_bot1.sqlite 123456

    # Dry run to see what would be imported
    python util/merge_databases.py secretlounge.sqlite old_bot2.sqlite 789012 --dry-run

    # Only import users, skip message mappings
    python util/merge_databases.py secretlounge.sqlite old_bot3.sqlite 345678 --skip-mappings
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from typing import Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.database import SQLiteDatabase

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)

class DatabaseMerger:
    def __init__(self, target_path: str, source_path: str, bot_id: int, dry_run: bool = False):
        self.target_path = target_path
        self.source_path = source_path
        self.bot_id = bot_id
        self.dry_run = dry_run
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source database not found: {source_path}")
        
        logging.info(f"Target database: {target_path}")
        logging.info(f"Source database: {source_path}")
        logging.info(f"Bot ID: {bot_id}")
        if dry_run:
            logging.info("DRY RUN MODE - no changes will be made")
        
        # Open databases
        self.target_db = SQLiteDatabase(target_path)
        self.source_conn = sqlite3.connect(source_path)
        self.source_conn.row_factory = sqlite3.Row
        
    def close(self):
        """Close database connections"""
        if hasattr(self, 'target_db'):
            self.target_db.close()
        if hasattr(self, 'source_conn'):
            self.source_conn.close()
    
    def get_existing_user_ids(self) -> Set[int]:
        """Get set of user IDs that already exist in target database"""
        user_ids = set()
        for uid in self.target_db.iterateUserIds():
            user_ids.add(uid)
        return user_ids
    
    def import_users(self) -> Tuple[int, int]:
        """
        Import users from source to target database.
        Returns: (imported_count, skipped_count)
        """
        logging.info("=" * 60)
        logging.info("Importing users...")
        
        existing_ids = self.get_existing_user_ids()
        logging.info(f"Target database has {len(existing_ids)} existing users")
        
        cur = self.source_conn.execute("SELECT * FROM users")
        imported = 0
        skipped = 0
        
        for row in cur:
            uid = row["id"]
            
            if uid in existing_ids:
                skipped += 1
                logging.debug(f"Skipping existing user {uid}")
                continue
            
            # Import user
            if not self.dry_run:
                # Use the database's internal user representation
                from src.database import User
                user = User()
                user.id = row["id"]
                user.username = row["username"]
                user.realname = row["realname"]
                user.rank = row["rank"]
                
                # Handle datetime fields
                user.joined = datetime.fromisoformat(row["joined"]) if row["joined"] else datetime.now()
                user.left = datetime.fromisoformat(row["left"]) if row["left"] else None
                user.lastActive = datetime.fromisoformat(row["lastActive"]) if row["lastActive"] else user.joined
                user.cooldownUntil = datetime.fromisoformat(row["cooldownUntil"]) if row["cooldownUntil"] else None
                user.warnExpiry = datetime.fromisoformat(row["warnExpiry"]) if row["warnExpiry"] else None
                
                user.blacklistReason = row["blacklistReason"]
                user.warnings = row["warnings"]
                user.karma = row["karma"]
                user.hideKarma = bool(row["hideKarma"])
                user.debugEnabled = bool(row["debugEnabled"])
                user.tripcode = row["tripcode"]
                
                self.target_db.addUser(user)
            
            imported += 1
            if imported % 100 == 0:
                logging.info(f"Imported {imported} users...")
        
        logging.info(f"Users imported: {imported}, skipped: {skipped}")
        return imported, skipped
    
    def import_message_mappings(self) -> Tuple[int, int]:
        """
        Import message mappings from source to target database with bot_id.
        Returns: (imported_count, skipped_count)
        """
        logging.info("=" * 60)
        logging.info("Importing message mappings...")
        
        # Check if source has message_mapping table
        cur = self.source_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='message_mapping'"
        )
        if not cur.fetchone():
            logging.warning("Source database has no message_mapping table, skipping")
            return 0, 0
        
        # Get existing mappings in target (to avoid duplicates)
        existing_mappings = set()
        if not self.dry_run:
            cur = self.target_db.db.execute(
                "SELECT msid, uid, message_id FROM message_mapping WHERE bot_id = ?",
                (self.bot_id,)
            )
            for row in cur:
                existing_mappings.add((row[0], row[1], row[2]))
        
        logging.info(f"Target has {len(existing_mappings)} existing mappings for bot_id {self.bot_id}")
        
        # Import mappings
        cur = self.source_conn.execute("SELECT * FROM message_mapping")
        imported = 0
        skipped = 0
        
        for row in cur:
            msid = row["msid"]
            uid = row["uid"]
            message_id = row["message_id"]
            
            if (msid, uid, message_id) in existing_mappings:
                skipped += 1
                continue
            
            if not self.dry_run:
                # Insert with bot_id
                created_at = row.get("created_at")
                if created_at:
                    created_at = datetime.fromisoformat(created_at)
                else:
                    created_at = datetime.now()
                
                self.target_db.save_message_mapping(uid, msid, message_id, bot_id=self.bot_id)
            
            imported += 1
            if imported % 1000 == 0:
                logging.info(f"Imported {imported} message mappings...")
        
        logging.info(f"Message mappings imported: {imported}, skipped: {skipped}")
        return imported, skipped
    
    def import_bot_users(self) -> Tuple[int, int]:
        """
        Import bot_users data from source to target database.
        Returns: (imported_count, updated_count)
        """
        logging.info("=" * 60)
        logging.info("Importing bot_users...")
        
        # Check if source has bot_users table
        cur = self.source_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bot_users'"
        )
        if not cur.fetchone():
            logging.warning("Source database has no bot_users table, skipping")
            return 0, 0
        
        # Get existing bot_users for this bot_id
        existing = {}
        if not self.dry_run:
            cur = self.target_db.db.execute(
                "SELECT uid, last_seen, can_send FROM bot_users WHERE bot_id = ?",
                (self.bot_id,)
            )
            for row in cur:
                existing[row[0]] = (row[1], row[2])
        
        logging.info(f"Target has {len(existing)} existing bot_users for bot_id {self.bot_id}")
        
        # Import bot_users
        cur = self.source_conn.execute("SELECT * FROM bot_users")
        imported = 0
        updated = 0
        
        for row in cur:
            uid = row["uid"]
            last_seen = row["last_seen"]
            can_send = row["can_send"]
            
            # Check if we need to update or insert
            if uid in existing:
                existing_last_seen, existing_can_send = existing[uid]
                # Update if source has newer last_seen or different can_send
                if last_seen > existing_last_seen or can_send != existing_can_send:
                    if not self.dry_run:
                        self.target_db.db.execute(
                            "UPDATE bot_users SET last_seen = ?, can_send = ? "
                            "WHERE bot_id = ? AND uid = ?",
                            (last_seen, can_send, self.bot_id, uid)
                        )
                    updated += 1
            else:
                # Insert new entry
                if not self.dry_run:
                    self.target_db.db.execute(
                        "INSERT INTO bot_users (bot_id, uid, last_seen, can_send) "
                        "VALUES (?, ?, ?, ?)",
                        (self.bot_id, uid, last_seen, can_send)
                    )
                imported += 1
            
            if (imported + updated) % 100 == 0:
                logging.info(f"Processed {imported + updated} bot_users...")
        
        if not self.dry_run:
            self.target_db.db.commit()
        
        logging.info(f"Bot_users imported: {imported}, updated: {updated}")
        return imported, updated
    
    def merge(self, skip_users=False, skip_mappings=False, skip_bot_users=False):
        """
        Perform the complete merge operation
        """
        try:
            stats = {
                "users_imported": 0,
                "users_skipped": 0,
                "mappings_imported": 0,
                "mappings_skipped": 0,
                "bot_users_imported": 0,
                "bot_users_updated": 0,
            }
            
            if not skip_users:
                stats["users_imported"], stats["users_skipped"] = self.import_users()
            else:
                logging.info("Skipping user import")
            
            if not skip_mappings:
                stats["mappings_imported"], stats["mappings_skipped"] = self.import_message_mappings()
            else:
                logging.info("Skipping message mapping import")
            
            if not skip_bot_users:
                stats["bot_users_imported"], stats["bot_users_updated"] = self.import_bot_users()
            else:
                logging.info("Skipping bot_users import")
            
            # Final commit if not dry run
            if not self.dry_run:
                self.target_db.db.commit()
                logging.info("Changes committed to target database")
            
            # Print summary
            logging.info("=" * 60)
            logging.info("MERGE SUMMARY:")
            logging.info(f"  Users:           {stats['users_imported']} imported, {stats['users_skipped']} skipped")
            logging.info(f"  Message mappings: {stats['mappings_imported']} imported, {stats['mappings_skipped']} skipped")
            logging.info(f"  Bot users:        {stats['bot_users_imported']} imported, {stats['bot_users_updated']} updated")
            
            if self.dry_run:
                logging.info("DRY RUN - no actual changes were made")
            else:
                logging.info("Merge completed successfully!")
            
        except Exception as e:
            logging.error(f"Error during merge: {e}", exc_info=True)
            raise
        finally:
            self.close()


def usage():
    print(__doc__)


def main():
    if len(sys.argv) < 4:
        usage()
        sys.exit(1)
    
    target_db = sys.argv[1]
    source_db = sys.argv[2]
    
    try:
        bot_id = int(sys.argv[3])
    except ValueError:
        print(f"Error: bot_id must be an integer, got: {sys.argv[3]}")
        sys.exit(1)
    
    # Parse flags
    dry_run = "--dry-run" in sys.argv
    skip_users = "--skip-users" in sys.argv
    skip_mappings = "--skip-mappings" in sys.argv
    skip_bot_users = "--skip-bot-users" in sys.argv
    
    merger = DatabaseMerger(target_db, source_db, bot_id, dry_run=dry_run)
    merger.merge(
        skip_users=skip_users,
        skip_mappings=skip_mappings,
        skip_bot_users=skip_bot_users
    )


if __name__ == "__main__":
    main()
