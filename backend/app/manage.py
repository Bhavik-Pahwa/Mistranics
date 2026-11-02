"""Run immutable, numbered SQL migrations and seed the file-backed registry."""

import argparse
from pathlib import Path
from sqlalchemy import text
from .config import Settings
from .db import connect
from .services import load_registry, seed


def migrate(engine):
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Deployment migrations require PostgreSQL")
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(6874312)"))
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        for path in sorted(
            (Path(__file__).resolve().parent.parent / "migrations").glob("*.sql")
        ):
            if connection.scalar(
                text("SELECT version FROM schema_migrations WHERE version=:v"),
                {"v": path.name},
            ):
                continue
            connection.exec_driver_sql(path.read_text())
            connection.execute(
                text("INSERT INTO schema_migrations(version) VALUES (:v)"),
                {"v": path.name},
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed"])
    args = parser.parse_args()
    settings = Settings()
    engine, factory = connect(settings.database_url)
    if args.command == "migrate":
        migrate(engine)
    else:
        with factory.begin() as session:
            seed(session, load_registry(settings.registry_file))
    engine.dispose()


if __name__ == "__main__":
    main()
