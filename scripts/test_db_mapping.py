import os, sys, sqlite3
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)
from src.database import SQLiteDatabase

path = "secretlounge.sqlite"
print("Opening DB:", path)
db = SQLiteDatabase(path)

# Ensure schema has message_mapping and bot_id column
con = db.db
cur = con.execute("PRAGMA table_info(message_mapping);")
cols = [row[1] for row in cur]
print("message_mapping cols:", cols)

# Insert mapping scoped to bot_id and verify reads
uid = 999001
msid = 42
mid = 777001
bot_id = 424242

# Clean any old rows for this test
con.execute("DELETE FROM message_mapping WHERE uid = ? AND message_id = ?", (uid, mid))
con.commit()

# Save and read back
db.save_message_mapping(uid, msid, mid, bot_id=bot_id)
msid_out = db.get_msid_by_uid_message(uid, mid, bot_id=bot_id)
print("msid_out:", msid_out)

pairs = db.get_recipient_mappings_by_msid(msid, bot_id=bot_id)
print("pairs:", pairs)

print("OK")
