"""DB config loaded from backend/.env.

DB_ENV=local  -> uses LOCAL_DB_* (defaults to localhost / postgres)
DB_ENV=remote -> uses DB_* (default)
DATABASE_URL  -> overrides everything (handy for tests / CI)
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Resolve path to backend/.env
BACKEND_DIR = Path(r"I:\My Drive\Antigravity\Migration\csv_upload\backend")
ENV_PATH = BACKEND_DIR / ".env"

#print("Current Python file:", Path(__file__).resolve())
print("Parent folder:", BACKEND_DIR)
print(".env file path:", ENV_PATH)
print(".env file exists:", ENV_PATH.exists())


@dataclass(frozen=True)
class Settings:
    env: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    metadata_schema: str
    metadata_table: str
    database_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("DB_ENV", "remote").lower()
        prefix = "LOCAL_DB_" if env == "local" else "DB_"
        default = "postgres" if env == "local" else ""

        def get(name: str, fallback: str = default) -> str:
            return os.getenv(prefix + name, fallback)

        return cls(
            env=env,
            db_host=get("HOST", "localhost"),
            db_port=int(get("PORT", "5432")),
            db_name=get("NAME"),
            db_user=get("USER"),
            db_password=get("PASSWORD"),
            metadata_schema=os.getenv("METADATA_SCHEMA", "public"),
            metadata_table=os.getenv("METADATA_TABLE", "noname"),
            database_url=os.getenv("DATABASE_URL", ""),
        )

    def validate(self) -> None:
        if self.database_url:
            return
        required = {
            "DB_NAME": self.db_name,
            "DB_USER": self.db_user,
            "DB_HOST": self.db_host,
            "METADATA_TABLE": self.metadata_table,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing {', '.join(missing)} for DB_ENV='{self.env}'. Check {ENV_PATH}.")

    def get_database_url(self) -> URL:
        if self.database_url:
            return make_url(self.database_url)
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user or None,
            password=self.db_password or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name or None,
        )

    def get_masked_url(self) -> str:
        return self.get_database_url().render_as_string(hide_password=True)


# Settings must exist before the engine is built
settings = Settings.from_env()
settings.validate()


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.get_database_url(), pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def check_connection() -> bool:
    """Try to connect to the database and report the result."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Connected! [{settings.env}] {settings.get_masked_url()}")
        return True
    except (SQLAlchemyError, OSError) as error:
        print(f"Connection failed: {type(error).__name__}: {error}")
        return False


if __name__ == "__main__":
    check_connection()