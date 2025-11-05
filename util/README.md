# Database Utilities

This directory contains utility scripts for managing SecretLounge-NG databases.

## merge_databases.py

Consolidate multiple SecretLounge database instances into a single unified database. This is particularly useful when migrating from separate database files per bot instance to a unified multi-bot database.

### Features

- Merges users, message mappings, and bot_users data
- Handles bot_id scoping for multi-instance support
- Prevents duplicate entries
- Updates existing records when source has newer data
- Dry-run mode for previewing changes
- Selective import (skip users, mappings, or bot_users)

### Usage

```bash
python util/merge_databases.py <target_db> <source_db> <bot_id> [options]
```

**Arguments:**
- `target_db` - Path to the target SQLite database (will be created if missing)
- `source_db` - Path to the source SQLite database to import from
- `bot_id` - Bot ID to assign to imported message mappings and bot_users

**Options:**
- `--dry-run` - Show what would be imported without making changes
- `--skip-users` - Skip importing users (only import message mappings/bot_users)
- `--skip-mappings` - Skip importing message mappings
- `--skip-bot-users` - Skip importing bot_users table

### Examples

**Basic merge:**
```bash
# Import database from old bot instance with bot_id 123456789
python util/merge_databases.py secretlounge.sqlite old_bot1.sqlite 123456789
```

**Dry run to preview:**
```bash
# See what would be imported without making changes
python util/merge_databases.py secretlounge.sqlite old_bot2.sqlite 987654321 --dry-run
```

**Skip certain tables:**
```bash
# Only import users, skip message mappings and bot_users
python util/merge_databases.py secretlounge.sqlite old_bot3.sqlite 111222333 \
  --skip-mappings --skip-bot-users
```

### Migration Workflow

When consolidating multiple bot instances into one database:

1. **Backup everything first:**
   ```bash
   cp secretlounge.sqlite secretlounge.sqlite.backup
   cp old_bot1.sqlite old_bot1.sqlite.backup
   ```

2. **Run a dry-run to preview:**
   ```bash
   python util/merge_databases.py secretlounge.sqlite old_bot1.sqlite 123456789 --dry-run
   ```

3. **Perform the actual merge:**
   ```bash
   python util/merge_databases.py secretlounge.sqlite old_bot1.sqlite 123456789
   ```

4. **Repeat for each additional instance:**
   ```bash
   python util/merge_databases.py secretlounge.sqlite old_bot2.sqlite 987654321
   python util/merge_databases.py secretlounge.sqlite old_bot3.sqlite 555666777
   ```

5. **Update your config.yaml:**
   - Make sure all bot instances point to the unified `secretlounge.sqlite`
   - Ensure each instance has the correct `bot_id` configured
   - Set one instance as `is_leader: true` for scheduled tasks

### How It Works

**Users:**
- User records are shared across all bot instances
- Existing users are skipped (no duplicates)
- Cooldowns and blacklists remain shared across instances

**Message Mappings:**
- Maps message IDs to users for reaction mirroring and pin/unpin
- Scoped by `bot_id` so each instance tracks its own messages
- Existing mappings for the same bot_id are skipped

**Bot Users:**
- Tracks which users have started/interacted with each bot
- Scoped by `bot_id` for per-instance reachability
- Updates existing records if source has newer data

### Output

The script provides detailed logging:
```
[2025-11-05 12:34:56] INFO: Target database: secretlounge.sqlite
[2025-11-05 12:34:56] INFO: Source database: old_bot1.sqlite
[2025-11-05 12:34:56] INFO: Bot ID: 123456789
============================================================
[2025-11-05 12:34:56] INFO: Importing users...
[2025-11-05 12:34:56] INFO: Users imported: 42, skipped: 3
============================================================
[2025-11-05 12:34:57] INFO: Importing message mappings...
[2025-11-05 12:34:57] INFO: Message mappings imported: 1523, skipped: 0
============================================================
[2025-11-05 12:34:58] INFO: Importing bot_users...
[2025-11-05 12:34:58] INFO: Bot_users imported: 38, updated: 4
============================================================
[2025-11-05 12:34:58] INFO: MERGE SUMMARY:
[2025-11-05 12:34:58] INFO:   Users:           42 imported, 3 skipped
[2025-11-05 12:34:58] INFO:   Message mappings: 1523 imported, 0 skipped
[2025-11-05 12:34:58] INFO:   Bot users:        38 imported, 4 updated
[2025-11-05 12:34:58] INFO: Merge completed successfully!
```

## Other Utilities

- **import.py** - Import from legacy SecretLounge JSON databases
- **blacklist.py** - Bulk blacklist operations
- **perms.py** - Permission management utilities

## Notes

- Always backup your databases before running merge operations
- Use `--dry-run` first to preview changes
- The target database will be created if it doesn't exist
- Message mappings and bot_users are scoped by bot_id to support multi-instance setups
- Users, cooldowns, and blacklists are shared across all instances
