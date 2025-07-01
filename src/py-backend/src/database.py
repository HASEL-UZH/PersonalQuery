from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import sqlite3
import os
from pathlib import Path

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
DB_PATH = APPDATA_PATH / "personal-query" / "database.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_engine = None
_db_instance = None


def get_db():
    global _engine, _db_instance

    if _db_instance is None:
        if not DB_PATH.exists():
            raise FileNotFoundError("PersonalQuery database does not exist.")

        readonly_connection = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro",
            uri=True,
            check_same_thread=False
        )
        _engine = create_engine(
            "sqlite://",
            creator=lambda: readonly_connection,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        _db_instance = SQLDatabase(_engine)

    return _db_instance
