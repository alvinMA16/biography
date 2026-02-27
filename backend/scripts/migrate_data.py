"""
SQLite → PostgreSQL 数据迁移工具

用法:
    cd backend
    python scripts/migrate_data.py --sqlite biography.db --pg postgresql://user:pass@host:5432/dbname

按外键依赖顺序导入:
    User → Conversation → Message → Memoir → TopicCandidate → GreetingCandidate
"""

import argparse
import sys
from datetime import datetime

from sqlalchemy import create_engine, text, inspect


# Table migration order (respects foreign key dependencies)
TABLES_IN_ORDER = [
    "users",
    "conversations",
    "messages",
    "memoirs",
    "topic_candidates",
    "greeting_candidates",
]


def migrate(sqlite_url: str, pg_url: str, dry_run: bool = False):
    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(pg_url)

    sqlite_inspector = inspect(sqlite_engine)
    sqlite_tables = set(sqlite_inspector.get_table_names())

    with sqlite_engine.connect() as src, pg_engine.connect() as dst:
        for table in TABLES_IN_ORDER:
            if table not in sqlite_tables:
                print(f"  SKIP {table} (not in SQLite)")
                continue

            rows = src.execute(text(f"SELECT * FROM {table}")).fetchall()
            columns = src.execute(text(f"SELECT * FROM {table} LIMIT 0")).keys()
            col_list = list(columns)

            if not rows:
                print(f"  SKIP {table} (0 rows)")
                continue

            if dry_run:
                print(f"  [DRY RUN] {table}: {len(rows)} rows")
                continue

            # Clear existing data in target table
            dst.execute(text(f"DELETE FROM {table}"))

            # Build parameterized INSERT
            cols = ", ".join(col_list)
            params = ", ".join(f":{c}" for c in col_list)
            insert_sql = text(f"INSERT INTO {table} ({cols}) VALUES ({params})")

            batch = []
            for row in rows:
                record = dict(zip(col_list, row))
                batch.append(record)

            dst.execute(insert_sql, batch)
            dst.commit()
            print(f"  OK   {table}: {len(rows)} rows migrated")

    print("\nDone!")


def main():
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="SQLite file path (e.g. biography.db)")
    parser.add_argument("--pg", required=True, help="PostgreSQL URL (e.g. postgresql://user:pass@host/db)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")
    args = parser.parse_args()

    sqlite_url = args.sqlite
    if not sqlite_url.startswith("sqlite"):
        sqlite_url = f"sqlite:///{sqlite_url}"

    print(f"Migrating from {sqlite_url}")
    print(f"           to   {args.pg}")
    print()

    migrate(sqlite_url, args.pg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
