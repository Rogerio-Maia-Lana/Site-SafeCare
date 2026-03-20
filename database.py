
import os
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


def init_db():
    schema_path = Path(__file__).with_name("schema_postgres.sql")
    sql = schema_path.read_text(encoding="utf-8")
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                for statement in [s.strip() for s in sql.split(";") if s.strip()]:
                    cur.execute(statement)
    finally:
        conn.close()
