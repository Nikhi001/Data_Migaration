"""Application Configuration Module.

Loads database and table configurations from backend/.env, performs validation,
and securely constructs the SQLAlchemy database URL without exposing secrets.
Supports both local and remote environments via DB_ENV=local | remote.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

# Resolve path to backend/.env
BACKEND_DIR = Path(r"I:\My Drive\Antigravity\Migration\tts_metadata\backend")
ENV_PATH = BACKEND_DIR / ".env"

# #print("Current Python file:", Path(__file__).resolve())
# print("Parent folder:", BACKEND_DIR)
# print(".env file path:", ENV_PATH)
# print(".env file exists:", ENV_PATH.exists())

# Load environment variables (override=True so .env changes are picked up)
load_dotenv(dotenv_path=ENV_PATH, override=True)


def _get_str(name: str, default: str = "") -> str:
    """Safely get stripped environment variable string."""
    val = os.getenv(name)
    return val.strip() if val is not None else default


def _get_int(name: str, default: int = 5432) -> int:
    """Safely get integer environment variable."""
    val = os.getenv(name)
    if val is not None and val.strip().isdigit():
        return int(val.strip())
    return default


@dataclass(frozen=True)
class Settings:
    """Application settings with environment switcher (local / remote)."""

    # Environment selector: 'local' or 'remote'
    db_env: str
    database_url_raw: str

    # Active Database connection parameters
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # Metadata schema and table parameters
    metadata_schema: str
    metadata_table: str

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment variables."""
        db_env = _get_str("DB_ENV", "remote").lower()
        database_url_raw = _get_str("DATABASE_URL", "")

        schema = _get_str("METADATA_SCHEMA", "public")
        table = _get_str("METADATA_TABLE", "tts_metadata")

        if db_env == "local":
            # Local development defaults (e.g. local Docker or PostgreSQL)
            host = _get_str("LOCAL_DB_HOST", "localhost")
            port = _get_int("LOCAL_DB_PORT", 5432)
            name = _get_str("LOCAL_DB_NAME", "test_tts")
            user = _get_str("LOCAL_DB_USER", "postgres")
            password = _get_str("LOCAL_DB_PASSWORD", "docker123")
        else:
            # Remote / production configuration
            host = _get_str("DB_HOST", "localhost")
            port = _get_int("DB_PORT", 5432)
            name = _get_str("DB_NAME", "")
            user = _get_str("DB_USER", "")
            password = _get_str("DB_PASSWORD", "")

        return cls(
            db_env=db_env,
            database_url_raw=database_url_raw,
            db_host=host,
            db_port=port,
            db_name=name,
            db_user=user,
            db_password=password,
            metadata_schema=schema,
            metadata_table=table,
        )

    def validate(self) -> None:
        """Validate required settings, raising clean errors without secrets."""
        if self.database_url_raw:
            return

        missing = []
        if not self.db_name:
            missing.append("DB_NAME" if self.db_env != "local" else "LOCAL_DB_NAME")
        if not self.db_user:
            missing.append("DB_USER" if self.db_env != "local" else "LOCAL_DB_USER")
        if not self.db_host:
            missing.append("DB_HOST" if self.db_env != "local" else "LOCAL_DB_HOST")
        if not self.metadata_table:
            missing.append("METADATA_TABLE")

        if missing:
            raise ValueError(
                f"Missing required database configuration ({self.db_env} mode): {', '.join(missing)}. "
                f"Please update backend/.env accordingly."
            )

    def get_database_url(self) -> URL:
        """Construct the SQLAlchemy database URL safely."""
        if self.database_url_raw:
            url = make_url(self.database_url_raw)
            if url.drivername == "postgresql":
                return url.set(drivername="postgresql+psycopg")
            return url

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user or None,
            password=self.db_password or None,
            host=self.db_host or "localhost",
            port=self.db_port,
            database=self.db_name or None,
        )

    def get_masked_url(self) -> str:
        """Return a sanitized connection string safe for logging or display."""
        return (
            f"postgresql+psycopg://{self.db_user}:***@{self.db_host}:{self.db_port}/{self.db_name}"
        )


# Singleton instance
settings = Settings.load()
