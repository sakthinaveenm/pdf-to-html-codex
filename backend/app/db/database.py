from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Integer, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.config.settings import settings

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    checksum: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='QUEUED', index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)

class Revision(Base):
    __tablename__ = 'revisions'
    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    ast: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)

class Annotation(Base):
    __tablename__ = 'annotations'
    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[str] = mapped_column(Text)

engine = create_engine(f'sqlite:///{settings.storage / "jobs.sqlite"}', connect_args={'check_same_thread': False, 'timeout': 30})
Session = sessionmaker(engine, expire_on_commit=False)

def initialize() -> None:
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text('PRAGMA journal_mode=WAL'))
    Base.metadata.create_all(engine)
