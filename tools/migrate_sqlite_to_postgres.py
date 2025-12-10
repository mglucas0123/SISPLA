import argparse
import json
import sqlite3
from typing import Dict, List, Sequence, Tuple

import psycopg2
import psycopg2.extras

DEFAULT_TABLE_ORDER = [
    "permission_catalog",
    "permissions",
    "roles",
    "role_permissions",
    "user_permissions",
    "users",
    "user_roles",
    "job_positions",
    "user_managers",
    "forms",
    "repositories",
    "repository_access",
    "files",
    "courses",
    "course_enrollment_terms",
    "quizzes",
    "questions",
    "answer_options",
    "quiz_attachments",
    "user_quiz_attempts",
    "user_course_progress",
    "notices",
    "nir",
    "nir_section_status",
    "nir_procedures",
    "suppliers",
    "supplier_evaluations",
    "supplier_evaluators",
    "supplier_issue_tracking",
    "employee_evaluations",
    "career_plans",
    "counter_evaluations",
    "validation_sessions",
]


def load_sqlite_rows(conn: sqlite3.Connection, table: str) -> Tuple[List[str], List[Tuple]]:
    cur = conn.execute(f'SELECT * FROM {table}')
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    return columns, rows


def postgres_columns(pg_cur, table: str) -> Dict[str, str]:
    pg_cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return {r[0]: r[1] for r in pg_cur.fetchall()}


def truncate_table(pg_cur, table: str) -> None:
    pg_cur.execute(f'DELETE FROM "{table}"')


def insert_rows(pg_cur, table: str, columns: Sequence[str], rows: Sequence[Tuple]) -> None:
    col_list = ", ".join(f'"{c}"' for c in columns)
    query = f'INSERT INTO "{table}" ({col_list}) VALUES %s'
    psycopg2.extras.execute_values(pg_cur, query, rows, page_size=200)


def reset_sequence(pg_cur, table: str, columns: Sequence[str]) -> None:
    if "id" not in columns:
        return
    pg_cur.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence(%s, 'id'),
            COALESCE((SELECT MAX(id) FROM "{table}"), 0) + 1,
            false
        )
        """,
        (f'"{table}"',),
    )


def migrate(sqlite_path: str, pg_dsn: str, table_order: List[str]) -> Dict[str, Dict[str, int]]:
    report: Dict[str, Dict[str, int]] = {}
    sqlite_conn = sqlite3.connect(sqlite_path)
    pg_conn = psycopg2.connect(pg_dsn)
    try:
        pg_cur = pg_conn.cursor()
        pg_cur.execute("SET session_replication_role = 'replica'")
        for table in table_order:
            sqlite_cols, rows = load_sqlite_rows(sqlite_conn, table)
            pg_cols = postgres_columns(pg_cur, table)
            common_cols = [c for c in sqlite_cols if c in pg_cols]
            if not common_cols:
                report[table] = {"copied": 0, "skipped": 0}
                continue
            truncate_table(pg_cur, table)

            def convert_value(col: str, value):
                if pg_cols.get(col) == "boolean" and isinstance(value, (int, float)):
                    return bool(value)
                return value

            filtered_rows = [
                tuple(convert_value(col, row[sqlite_cols.index(col)]) for col in common_cols)
                for row in rows
            ]
            if filtered_rows:
                insert_rows(pg_cur, table, common_cols, filtered_rows)
            reset_sequence(pg_cur, table, common_cols)
            report[table] = {"copied": len(filtered_rows), "skipped": len(rows) - len(filtered_rows)}
        pg_cur.execute("SET session_replication_role = 'origin'")
        pg_conn.commit()
    finally:
        sqlite_conn.close()
        pg_conn.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="Path to SQLite database file")
    parser.add_argument("--postgres", required=True, help="PostgreSQL DSN")
    parser.add_argument(
        "--tables",
        nargs="*",
        help="Optional explicit table order (default uses built-in list)",
    )
    args = parser.parse_args()

    tables = args.tables if args.tables else DEFAULT_TABLE_ORDER
    report = migrate(args.sqlite, args.postgres, tables)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
