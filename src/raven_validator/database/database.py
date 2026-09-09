"""Async-capable database manager — auto-creates schema on first run."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from raven_validator.database.models import Base


class Database:
    """Wraps SQLAlchemy engine + session factory."""

    def __init__(self, db_url: str) -> None:
        # Ensure parent directory exists for file-based SQLite.
        if db_url.startswith("sqlite") and ":///" in db_url:
            path_part = db_url.split(":///", 1)[1].split("?", 1)[0]
            if path_part and path_part != ":memory:":
                Path(path_part).parent.mkdir(parents=True, exist_ok=True)

        connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
        self.engine = create_engine(db_url, connect_args=connect_args, future=True)
        self._factory = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, future=True
        )
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        sess = self._factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def dispose(self) -> None:
        self.engine.dispose()
