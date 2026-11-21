from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, event, String, Text, ForeignKey, JSON, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, connect_args={'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}, pool_pre_ping=True)
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_pragmas(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=10000')

Session = sessionmaker(engine, expire_on_commit=False)


class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Submission(Base):
    __tablename__ = 'submissions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    skipped: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SourceFile(Base):
    __tablename__ = 'source_files'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id', ondelete='CASCADE'), index=True)
    path: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)


class AnalysisJob(Base):
    __tablename__ = 'analysis_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id', ondelete='CASCADE'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    stage: Mapped[str] = mapped_column(String(100), default='Waiting for worker')
    request: Mapped[dict] = mapped_column(JSON)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ModelRun(Base):
    __tablename__ = 'model_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('analysis_jobs.id', ondelete='CASCADE'), index=True)
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default='running')
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_response: Mapped[str] = mapped_column(Text, default='')
    error: Mapped[str] = mapped_column(Text, default='')


class Finding(Base):
    __tablename__ = 'findings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('model_runs.id', ondelete='CASCADE'), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class GeneratedArtifact(Base):
    __tablename__ = 'generated_artifacts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('model_runs.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict] = mapped_column(JSON)


class FindingFeedback(Base):
    __tablename__ = 'finding_feedback'
    finding_id: Mapped[str] = mapped_column(ForeignKey('findings.id', ondelete='CASCADE'), primary_key=True)
    verdict: Mapped[str] = mapped_column(String(30))
