#!/usr/bin/env python
"""CLI tool to ingest incident CSV files into GridSignal Mini SQLite database."""

import sys
import argparse
from pathlib import Path
from app.config import SEED_CSV_PATH, DB_PATH
from app.database import init_db, get_connection
from app.ingest import ingest_csv

def main():
    parser = argparse.ArgumentParser(description="Ingest incident CSV into GridSignal Mini")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(SEED_CSV_PATH),
        help="Path to CSV file (defaults to data/seed_incidents.csv)"
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Initializing database at: {DB_PATH}")
    init_db()

    conn = get_connection()
    try:
        print(f"Starting ingestion from: {csv_path}")
        stats = ingest_csv(csv_path, conn)
        print("\n--- INGESTION SUMMARY ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
