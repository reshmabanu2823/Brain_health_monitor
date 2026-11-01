from sqlalchemy import String, Integer, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, uid, now

class SchemaVersion(Base):
    __tablename__ = 'schema_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int]

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)

class AuthToken(Base):
    __tablename__ = 'auth_tokens'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires: Mapped[float]

class Device(Base):
    __tablename__ = 'eeg_devices'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)

class Recording(Base):
    __tablename__ = 'recording_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey('eeg_devices.id'), nullable=True)
    state: Mapped[str] = mapped_column(default='recording')
    started_at: Mapped[str] = mapped_column(default=now)
    ended_at: Mapped[str | None]
    end_reason: Mapped[str | None]
    context: Mapped[dict] = mapped_column(JSON)
    config: Mapped[dict] = mapped_column(JSON)
    raw_path: Mapped[str]
    sample_count: Mapped[int] = mapped_column(default=0)
    missing_samples: Mapped[int] = mapped_column(default=0)
    valid_windows: Mapped[int] = mapped_column(default=0)
    invalid_windows: Mapped[int] = mapped_column(default=0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)

class Segment(Base):
    __tablename__ = 'processed_segments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey('recording_sessions.id'), index=True)
    start_index: Mapped[int]
    end_index: Mapped[int]
    created_at: Mapped[str] = mapped_column(default=now)
    result: Mapped[dict] = mapped_column(JSON)

class Feature(Base):
    __tablename__ = 'extracted_features'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    segment_id: Mapped[str] = mapped_column(ForeignKey('processed_segments.id'), index=True)
    values: Mapped[dict] = mapped_column(JSON)

class Baseline(Base):
    __tablename__ = 'personalized_baselines'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    session_ids: Mapped[list] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    config: Mapped[dict] = mapped_column(JSON)
    statistics: Mapped[dict] = mapped_column(JSON)

class Anomaly(Base):
    __tablename__ = 'anomaly_records'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey('recording_sessions.id'), index=True)
    segment_id: Mapped[str | None] = mapped_column(ForeignKey('processed_segments.id'), nullable=True)
    category: Mapped[str]
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)

class MRIUpload(Base):
    __tablename__ = 'mri_uploads'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    filename: Mapped[str]
    private_path: Mapped[str]
    sha256: Mapped[str]

class MRIPrediction(Base):
    __tablename__ = 'mri_predictions'
    upload_id: Mapped[str] = mapped_column(ForeignKey('mri_uploads.id'), primary_key=True)
    result: Mapped[dict] = mapped_column(JSON)

class Explanation(Base):
    __tablename__ = 'ai_explanations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('recording_sessions.id'))
    created_at: Mapped[str] = mapped_column(default=now)
    evidence_digest: Mapped[str]
    result: Mapped[dict] = mapped_column(JSON)

class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey('recording_sessions.id'))
    created_at: Mapped[str] = mapped_column(default=now)
    format: Mapped[str]
    digest: Mapped[str]
