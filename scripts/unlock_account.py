"""Local administrator recovery: reset login lockout for one username."""
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
database = os.environ.get("DATABASE_PATH", str(PROJECT_ROOT / "instance" / "expense_claims.sqlite3"))
if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/unlock_account.py USERNAME")

conn = sqlite3.connect(database)
cur = conn.execute(
    "UPDATE users SET failed_attempts=0, locked_at=NULL WHERE username=?",
    (sys.argv[1].strip().lower(),),
)
conn.commit()
conn.close()
if cur.rowcount:
    print(f"Unlocked account: {sys.argv[1]}")
else:
    print(f"No account found: {sys.argv[1]}")
