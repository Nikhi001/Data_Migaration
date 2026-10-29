from sqlalchemy import Identity,Integer,String,Text,Date,Interval
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class TTSMetadata(Base):
    __tablename__ = "sanskrit"

    # Original CSV unqiue number
    ui_id: Mapped[int] = mapped_column(Integer,Identity(always=True),primary_key=True,)

    # Date and dataset information
    record_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_links: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vedic_accent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)


    # Duration fields
    actual_duration: Mapped[object | None] = mapped_column(Interval,nullable=True)
    processed_duration: Mapped[object | None] = mapped_column(Interval,nullable=True)
    total_audio_files: Mapped[int | None] = mapped_column(Integer,nullable=True)

    # Audio and dataset metadata
    meter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    multispeaker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    categories: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_through: Mapped[str | None] = mapped_column(String(255),nullable=True)
    researched_by: Mapped[str | None] = mapped_column(String(255),nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(String(100),nullable=True)

    # Links, workers and remarks
    text_links: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)