import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel Serverless File-System Compatibility
IS_VERCEL = bool(os.getenv("VERCEL"))
if IS_VERCEL:
    DB_PATH = Path("/tmp/db.sqlite3")
    SOURCE_DB = BASE_DIR / "db.sqlite3"
    # Copy pre-seeded database to writable /tmp directory on first cold start
    if SOURCE_DB.is_file() and not DB_PATH.is_file():
        try:
            shutil.copyfile(SOURCE_DB, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = BASE_DIR / "db.sqlite3"

DATA_DIR = BASE_DIR / "data"
SEED_CSV_PATH = DATA_DIR / "seed_incidents.csv"
REPLAY_CSV_PATH = DATA_DIR / "replay_batch.csv"
STATIC_DIR = BASE_DIR / "static"

# Correlation Thresholds (Both Boundaries Inclusive)
MAX_DISTANCE_FT: float = 200.0
MAX_TIME_GAP_MINUTES: float = 360.0  # 6.0 hours * 60 minutes

