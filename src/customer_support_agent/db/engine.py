"""SQLite engine setup with foreign-key enforcement."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event

from customer_support_agent.core.config import DEMO_DATABASE_PATH


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def create_sqlite_engine(database_path: Path = DEMO_DATABASE_PATH) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path}", future=True)
