"""Reset the local demo database and regenerate the eight users and 60 claims."""
from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DATABASE_PATH", str(PROJECT_ROOT / "instance" / "expense_claims.sqlite3"))

from app import create_app  # noqa: E402
from db import get_db  # noqa: E402

app = create_app({"SEED_DATA": False})
with app.app_context():
    db = get_db()
    db.execute("DROP TABLE IF EXISTS audit_log")
    db.execute("DROP TABLE IF EXISTS claims")
    db.execute("DROP TABLE IF EXISTS users")
    db.commit()
    from db import init_db
    init_db()
    from seed import seed_database
    seed_database(db)
    print("Demo database reset. Seeded 8 users and 60 claims.")
