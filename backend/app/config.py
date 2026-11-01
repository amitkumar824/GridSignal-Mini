import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "gridsignal.db"))

# Correlation thresholds (inclusive boundaries per specification)
MAX_DISTANCE_FT = 200.0
MAX_TIME_GAP_MINUTES = 360.0  # 6 hours * 60 minutes

# Default seed data files
SEED_CSV_PATH = BASE_DIR / "data" / "seed_incidents.csv"
REPLAY_CSV_PATH = BASE_DIR / "data" / "replay_batch.csv"

