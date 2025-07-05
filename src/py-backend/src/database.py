import shutil
import sys

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import sqlite3
import os
from pathlib import Path

from helper.env_loader import load_env

load_env()

db_path_str = os.getenv("PERSONALQUERY_DB_PATH")
if not db_path_str:
    raise RuntimeError("PERSONALQUERY_DB_PATH is not set in .env")
DB_PATH = Path(db_path_str)
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


def migrate_checkpoint_db(old_path: Path, new_path: Path):
    if not old_path.exists():
        return
    if new_path.exists():
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old_path, new_path)
    old_path.unlink()


def get_chat_db_path():
    if sys.platform == "darwin":
        new_checkpoint_dir = Path.home() / "Library" / "Application Support" / "personal-query"
    else:
        new_checkpoint_dir = Path(os.getenv("APPDATA", Path.home())) / "personal-query"
    return new_checkpoint_dir / "chat_checkpoints.db"


def get_app_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "personal-query"
    else:
        return Path(os.getenv("APPDATA", Path.home())) / "personal-query"


