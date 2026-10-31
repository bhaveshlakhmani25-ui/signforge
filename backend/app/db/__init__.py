from sqlmodel import Session, SQLModel, create_engine

from app.core import config as C

engine = create_engine(C.DATABASE_URL, connect_args={"check_same_thread": False} if C.DATABASE_URL.startswith("sqlite") else {})


def init_db():
    from app.db import models  # noqa: F401  registers tables

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
