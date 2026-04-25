from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Float, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship, sessionmaker

from .config import settings


def _utcnow() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"


class Job(Base):
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_filename: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    duration_s: Mapped[float | None] = mapped_column(Float)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    model: Mapped[str] = mapped_column(String, nullable=False, default="htdemucs")
    instrument: Mapped[str | None] = mapped_column(String)        # auto | guitar | violin
    complexity: Mapped[str] = mapped_column(String, nullable=False, default="full")  # full | simple
    created_at: Mapped[int] = mapped_column(Integer, default=_utcnow, nullable=False)
    completed_at: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String)

    stems: Mapped[list["Stem"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    outputs: Mapped[list["Output"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Stem(Base):
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    rms: Mapped[float | None] = mapped_column(Float)
    peak: Mapped[float | None] = mapped_column(Float)

    job: Mapped[Job] = relationship(back_populates="stems")


class Output(Base):
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    stem_id: Mapped[str | None] = mapped_column(ForeignKey("stems.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String, nullable=False)      # sheet | chords | tabs
    format: Mapped[str] = mapped_column(String, nullable=False)    # pdf | musicxml | midi | gp5 | ascii | cho
    path: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[int] = mapped_column(Integer, default=_utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="outputs")


class Event(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(String)
    ts: Mapped[int] = mapped_column(Integer, default=_utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="events")


settings.ensure_dirs()
engine = create_engine(settings.db_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _ensure_columns() -> None:
    """Tiny built-in migration: add columns we've added since the original schema.

    SQLAlchemy's `create_all` is a no-op when the table exists, so new columns
    on existing DBs need an explicit ALTER. Cheap to keep here while v1 ships.
    """
    insp = inspect(engine)
    if "jobs" not in insp.get_table_names():
        return
    existing = {col["name"] for col in insp.get_columns("jobs")}
    additions: list[str] = []
    if "complexity" not in existing:
        additions.append("ALTER TABLE jobs ADD COLUMN complexity TEXT NOT NULL DEFAULT 'full'")
    if not additions:
        return
    with engine.begin() as conn:
        for stmt in additions:
            conn.execute(text(stmt))


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_columns()
