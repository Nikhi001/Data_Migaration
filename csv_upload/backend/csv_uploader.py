"""Upload a TTS metadata CSV into PostgreSQL.

Usage:
    python upload_tts_metadata.py data.csv --batch-size 500
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import func, insert, select

from database import Base, SessionLocal, engine
from models import TTSMetadata


# --------------------------------------------------
# 1. Configuration
# --------------------------------------------------

# CSV header (after normalizing) -> database column
COLUMN_MAPPING = {
    "date": "record_date",
    "language": "language",
    "gender": "gender",
    "source": "source",
    "source_links": "source_links",
    "license_tag": "license_tag",
    "data_description": "data_description",
    "vedic_accent": "vedic_accent",
    "file_name": "file_name",
    "actual_duration": "actual_duration",
    "processed_duration": "processed_duration",
    "total_audio_files": "total_audio_files",
    "meter": "meter",
    "style": "style",
    "multispeaker": "multispeaker",
    "categories": "categories",
    "processed_through": "processed_through",
    "researched_by": "researched_by",
    "re-work_status": "status",
    "speaker_id": "speaker_id",
    "text_links": "text_links",
    "workers": "validated_by"
}


# --------------------------------------------------
# 2. Value parsers (database column name -> parser)
#    Any column not listed here is kept as a plain string.
# --------------------------------------------------

def parse_integer(value: str) -> int:
    number = float(value)
    if not number.is_integer():  # reject 2.5 instead of silently truncating
        raise ValueError("expected a whole number")
    return int(number)


def parse_date(value: str):
    return pd.to_datetime(value).date()


def parse_duration(value: str):
    """'01:25:30' or '1 days 02:30:00' -> timedelta (PostgreSQL INTERVAL)."""
    return pd.to_timedelta(value).to_pytimedelta()


PARSERS = {
    "total_audio_files": parse_integer,
    "record_date": parse_date,
    "actual_duration": parse_duration,
    "processed_duration": parse_duration,
}


# --------------------------------------------------
# 3. Read the CSV
# --------------------------------------------------

def normalize_header(name: str) -> str:
    """' Re-work Status ' -> 're-work_status'."""
    return re.sub(r"\s+", "_", str(name).strip().lower())


def read_csv(csv_path: Path) -> pd.DataFrame:
    """Read the CSV and return only the columns the database needs."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # utf-8-sig removes a BOM if present; dtype=str keeps values untouched.
    df = pd.read_csv(
        csv_path, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    df.columns = [normalize_header(c) for c in df.columns]

    if df.columns.duplicated().any():
        raise ValueError("Duplicate column names found. Fix the CSV headers.")

    missing = set(COLUMN_MAPPING) - set(df.columns)
    if missing:
        raise ValueError(
            "The CSV is missing these columns: " + ", ".join(sorted(missing))
        )

    # Keep mapped columns only, then rename them to database names.
    return df[list(COLUMN_MAPPING)].rename(columns=COLUMN_MAPPING)


# --------------------------------------------------
# 4. Convert rows
# --------------------------------------------------

def convert_row(row: dict, line_number: int) -> dict:
    """Clean blanks and convert one row to database-ready values."""
    converted = {}

    for column, value in row.items():
        value = value.strip() or None  # blank / whitespace-only -> None
        parser = PARSERS.get(column)

        if value is not None and parser is not None:
            try:
                value = parser(value)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(
                    f"Line {line_number}, column '{column}': "
                    f"invalid value {value!r} ({exc})"
                ) from exc

        converted[column] = value

    return converted


# --------------------------------------------------
# 5. Upload
# --------------------------------------------------

def upload_csv(csv_path: Path, batch_size: int = 500) -> None:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    df = read_csv(csv_path)
    if df.empty:
        print("The CSV contains no data rows. Nothing to upload.")
        return

    print(f"Rows found: {len(df)}. Validating...")

    # The CSV header is line 1, so the first data row is line 2.
    records = [
        convert_row(row, line_number)
        for line_number, row in enumerate(df.to_dict("records"), start=2)
    ]

    # Requires the target database to already exist.
    Base.metadata.create_all(bind=engine)

    # One transaction: if any batch fails, nothing is saved.
    with SessionLocal() as session, session.begin():
        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]
            session.execute(insert(TTSMetadata), batch)
            print(f"Inserted {start + len(batch)}/{len(records)} rows...")

    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(TTSMetadata))

    print(f"\nUpload complete. Rows in '{TTSMetadata.__tablename__}': {total}")


# --------------------------------------------------
# 6. Command-line entry point
# --------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload TTS metadata CSV to PostgreSQL."
    )
    parser.add_argument("csv_path", help="Path to the CSV file.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows inserted per batch (default: 500).",
    )
    args = parser.parse_args()

    try:
        upload_csv(Path(args.csv_path), args.batch_size)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()