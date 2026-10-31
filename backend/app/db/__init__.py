from sqlmodel import Session, SQLModel, create_engine

from app.core import config as C

engine = create_engine(C.DATABASE_URL, connect_args={"check_same_thread": False} if C.DATABASE_URL.startswith("sqlite") else {})


def init_db():
    from app.db import models  # noqa: F401  registers tables

    SQLModel.metadata.create_all(engine)
    add_missing_columns()


def add_missing_columns():
    """shortcut: not a migration system. Adds columns that exist in the models but not in an older local DB
    (with the model's default), so teammates' databases keep working after a pull. Never drops or alters anything.
    Upgrade to Alembic when the schema needs renames, type changes or Postgres."""
    from sqlalchemy import JSON, inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                sql_default = ("NULL" if default is None else "1" if default is True else "0" if default is False
                               else repr(default) if isinstance(default, (int, float)) else "'" + str(default).replace("'", "''") + "'")
                if isinstance(col.type, JSON):
                    sql_default = "'{}'"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(engine.dialect)} DEFAULT {sql_default}'))


def get_session():
    with Session(engine) as session:
        yield session
