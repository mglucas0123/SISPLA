import argparse
import json
import pathlib
import sqlite3
from typing import List, Dict

import psycopg2


def list_sqlite(path: str) -> List[Dict[str, int]]:
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur if not r[0].startswith("sqlite_")]
        info = []
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            info.append({"table": table, "rows": count})
        return info
    finally:
        conn.close()


def list_postgres(dsn: str) -> List[Dict[str, int]]:
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        tables = [r[0] for r in cur.fetchall()]
        info = []
        for table in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            count = cur.fetchone()[0]
            info.append({"table": table, "rows": count})
        return info
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect DB table counts")
    parser.add_argument("--sqlite", help="Path to SQLite database")
    parser.add_argument("--postgres", help="PostgreSQL DSN")
    args = parser.parse_args()

    output = {}
    if args.sqlite:
        output["sqlite"] = list_sqlite(args.sqlite)
    if args.postgres:
        output["postgres"] = list_postgres(args.postgres)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
