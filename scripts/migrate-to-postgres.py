#!/usr/bin/env python3
"""
ActivityWatch SQLite to PostgreSQL Migration Script

Migrates data from SQLite database to PostgreSQL.

Usage:
    python migrate-to-postgres.py --source <sqlite_db_path> --target <postgres_url>

Example:
    python migrate-to-postgres.py \
        --source ~/.local/share/aw-server/peewee-sqlite.v2.db \
        --target postgresql://user:password@localhost:5432/activitywatch

Requirements:
    - psycopg2 (pip install psycopg2-binary)
    - sqlite3 (usually included with Python)
    - aw-core (installed from source)
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("ERROR: psycopg2 not installed. Install it with:")
    print("  pip install psycopg2-binary")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class MigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.buckets_migrated = 0
        self.events_migrated = 0
        self.errors = []
        self.start_time = None
        self.end_time = None

    def elapsed_time(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def report(self):
        """Print migration report."""
        elapsed = self.elapsed_time()
        logger.info("=" * 70)
        logger.info("MIGRATION REPORT")
        logger.info("=" * 70)
        logger.info(f"Buckets migrated: {self.buckets_migrated}")
        logger.info(f"Events migrated:  {self.events_migrated}")
        logger.info(f"Errors:           {len(self.errors)}")
        if elapsed:
            logger.info(f"Time elapsed:     {elapsed:.2f} seconds")
        logger.info("=" * 70)

        if self.errors:
            logger.error("ERRORS ENCOUNTERED:")
            for error in self.errors:
                logger.error(f"  - {error}")


class SQLiteSource:
    """Read from SQLite source database."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to SQLite: {self.db_path}")

    def get_buckets(self) -> List[dict]:
        """Fetch all buckets from SQLite."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, id, created, name, type, client, hostname, datastr FROM bucketmodel")
        buckets = []
        for row in cursor.fetchall():
            buckets.append({
                "key": row[0],
                "id": row[1],
                "created": row[2],
                "name": row[3],
                "type": row[4],
                "client": row[5],
                "hostname": row[6],
                "datastr": row[7] or "{}",
            })
        logger.info(f"Found {len(buckets)} buckets in SQLite")
        return buckets

    def get_events_for_bucket(self, bucket_key: int, batch_size: int = 5000) -> List[dict]:
        """Fetch events for a bucket in batches."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, bucket, timestamp, duration, datastr FROM eventmodel WHERE bucket = ? ORDER BY id",
            (bucket_key,)
        )

        events = []
        for row in cursor.fetchall():
            events.append({
                "id": row[0],
                "bucket": row[1],
                "timestamp": row[2],
                "duration": row[3],
                "datastr": row[4],
            })

        logger.debug(f"Found {len(events)} events in bucket key={bucket_key}")
        return events

    def get_event_count(self) -> int:
        """Get total event count."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM eventmodel")
        return cursor.fetchone()[0]

    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("SQLite connection closed")


class PostgresTarget:
    """Write to PostgreSQL target database."""

    def __init__(self, database_url: str):
        try:
            self.conn = psycopg2.connect(database_url)
            logger.info(f"Connected to PostgreSQL: {database_url.split('@')[0]}@{database_url.split('@')[1] if '@' in database_url else 'N/A'}")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

        # Create tables if they don't exist
        self._create_tables()

    def _create_tables(self):
        """Create necessary tables in PostgreSQL."""
        cursor = self.conn.cursor()

        # Create bucketmodel table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bucketmodel (
                key SERIAL PRIMARY KEY,
                id VARCHAR(255) UNIQUE NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name VARCHAR(255),
                type VARCHAR(255) NOT NULL,
                client VARCHAR(255) NOT NULL,
                hostname VARCHAR(255) NOT NULL,
                datastr TEXT
            )
        """)

        # Create eventmodel table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventmodel (
                id SERIAL PRIMARY KEY,
                bucket INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                duration NUMERIC NOT NULL,
                datastr TEXT NOT NULL,
                FOREIGN KEY (bucket) REFERENCES bucketmodel(key) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS eventmodel_bucket_idx ON eventmodel(bucket)")
        cursor.execute("CREATE INDEX IF NOT EXISTS eventmodel_timestamp_idx ON eventmodel(timestamp)")

        self.conn.commit()
        logger.info("PostgreSQL tables created/verified")

    def clear_data(self):
        """Clear existing data in target database."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM eventmodel")
        cursor.execute("DELETE FROM bucketmodel")
        self.conn.commit()
        logger.info("Cleared existing data in PostgreSQL")

    def insert_bucket(self, bucket: dict) -> int:
        """Insert a bucket and return its key."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO bucketmodel (id, created, name, type, client, hostname, datastr)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING key
                """,
                (
                    bucket["id"],
                    bucket["created"],
                    bucket["name"],
                    bucket["type"],
                    bucket["client"],
                    bucket["hostname"],
                    bucket["datastr"],
                ),
            )
            new_key = cursor.fetchone()[0]
            self.conn.commit()
            return new_key
        except psycopg2.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to insert bucket {bucket['id']}: {e}")

    def insert_events_batch(self, events: List[dict], bucket_key_map: dict):
        """Insert a batch of events."""
        if not events:
            return

        cursor = self.conn.cursor()
        try:
            # Prepare data for batch insert
            data = [
                (
                    event["id"],
                    bucket_key_map[event["bucket"]],
                    event["timestamp"],
                    event["duration"],
                    event["datastr"],
                )
                for event in events
            ]

            # Use executemany for batch insert
            cursor.executemany(
                """
                INSERT INTO eventmodel (id, bucket, timestamp, duration, datastr)
                VALUES (%s, %s, %s, %s, %s)
                """,
                data,
            )
            self.conn.commit()
        except psycopg2.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to insert {len(events)} events: {e}")

    def verify_migration(self, source: SQLiteSource, stats: MigrationStats):
        """Verify that migration was successful."""
        cursor = self.conn.cursor()

        # Check bucket count
        cursor.execute("SELECT COUNT(*) FROM bucketmodel")
        pg_buckets = cursor.fetchone()[0]

        # Check event count
        cursor.execute("SELECT COUNT(*) FROM eventmodel")
        pg_events = cursor.fetchone()[0]

        logger.info(f"PostgreSQL: {pg_buckets} buckets, {pg_events} events")
        logger.info(f"Expected:   {stats.buckets_migrated} buckets, {stats.events_migrated} events")

        if pg_buckets != stats.buckets_migrated or pg_events != stats.events_migrated:
            logger.warning("⚠️  Row count mismatch after migration!")
            return False

        logger.info("✓ Migration verification successful")
        return True

    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("PostgreSQL connection closed")


def migrate(sqlite_path: str, postgres_url: str, clear_target: bool = False, batch_size: int = 5000):
    """
    Perform the migration from SQLite to PostgreSQL.

    Args:
        sqlite_path: Path to source SQLite database
        postgres_url: PostgreSQL connection URL
        clear_target: Whether to clear existing data in target database
        batch_size: Number of events to insert per batch
    """
    stats = MigrationStats()
    stats.start_time = datetime.now()

    try:
        # Connect to both databases
        source = SQLiteSource(sqlite_path)
        target = PostgresTarget(postgres_url)

        # Optional: Clear target database
        if clear_target:
            target.clear_data()

        # Get buckets from source
        buckets = source.get_buckets()
        bucket_key_map = {}  # Maps old SQLite keys to new PostgreSQL keys

        # Migrate buckets
        logger.info(f"Migrating {len(buckets)} buckets...")
        for bucket in buckets:
            try:
                new_key = target.insert_bucket(bucket)
                bucket_key_map[bucket["key"]] = new_key
                stats.buckets_migrated += 1
                logger.debug(f"Migrated bucket: {bucket['id']} (SQLite key {bucket['key']} → PostgreSQL key {new_key})")
            except Exception as e:
                logger.error(f"Error migrating bucket {bucket['id']}: {e}")
                stats.errors.append(str(e))

        # Migrate events
        total_events = source.get_event_count()
        logger.info(f"Migrating {total_events} events...")

        events_processed = 0
        for bucket in buckets:
            if bucket["key"] not in bucket_key_map:
                continue

            try:
                events = source.get_events_for_bucket(bucket["key"], batch_size)
                
                # Process in batches
                for i in range(0, len(events), batch_size):
                    batch = events[i : i + batch_size]
                    target.insert_events_batch(batch, bucket_key_map)
                    stats.events_migrated += len(batch)
                    events_processed += len(batch)

                    if events_processed % (batch_size * 10) == 0:
                        logger.info(f"Progress: {events_processed}/{total_events} events migrated")

            except Exception as e:
                logger.error(f"Error migrating events for bucket {bucket['id']}: {e}")
                stats.errors.append(str(e))

        logger.info(f"Completed event migration: {stats.events_migrated} events")

        # Verify migration
        target.verify_migration(source, stats)

        # Close connections
        source.close()
        target.close()

        stats.end_time = datetime.now()
        stats.report()

        if stats.errors:
            logger.warning(f"Migration completed with {len(stats.errors)} errors")
            return 1
        else:
            logger.info("✓ Migration completed successfully!")
            return 0

    except Exception as e:
        logger.error(f"Fatal error during migration: {e}")
        stats.errors.append(str(e))
        stats.end_time = datetime.now()
        stats.report()
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate ActivityWatch data from SQLite to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate using explicit database path
  %(prog)s --source ~/.local/share/aw-server/peewee-sqlite.v2.db \\
           --target postgresql://postgres:password@localhost:5432/activitywatch

  # Migrate using DATABASE_URL environment variable
  export DATABASE_URL=postgresql://user:pass@host:port/dbname
  %(prog)s --source /path/to/db.sqlite

  # Migrate with verbose output
  %(prog)s --source db.sqlite --target postgresql://localhost/aw --verbose

  # Clear target database before migrating
  %(prog)s --source db.sqlite --target postgresql://localhost/aw --clear
        """,
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Path to source SQLite database file",
    )
    parser.add_argument(
        "--target",
        help="Target PostgreSQL connection URL (or use DATABASE_URL env var)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data in target database before migrating",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Number of events to insert per batch (default: 5000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get target PostgreSQL URL
    target_url = args.target or os.environ.get("DATABASE_URL")
    if not target_url:
        parser.error("--target must be provided or DATABASE_URL environment variable must be set")

    # Confirm before proceeding
    print()
    print("⚠️  WARNING: This will migrate data from SQLite to PostgreSQL")
    print(f"   Source:      {args.source}")
    print(f"   Target:      {target_url}")
    if args.clear:
        print("   Action:      CLEAR target database before migrating")
    print()
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response not in ("yes", "y"):
        logger.info("Migration cancelled by user")
        return 0

    # Perform migration
    return migrate(args.source, target_url, clear_target=args.clear, batch_size=args.batch_size)


if __name__ == "__main__":
    sys.exit(main())
