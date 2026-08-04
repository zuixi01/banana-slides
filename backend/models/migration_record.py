"""Idempotency ledger for imports from legacy applications."""
import uuid
from datetime import datetime

from . import db


class MigrationRecord(db.Model):
    __tablename__ = 'deckforge_migration_records'
    __table_args__ = (
        db.UniqueConstraint('source_kind', 'source_id', name='uq_deckforge_migration_source'),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_kind = db.Column(db.String(30), nullable=False)
    source_id = db.Column(db.String(255), nullable=False)
    target_id = db.Column(db.String(36), nullable=True)
    checksum = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    details_json = db.Column(db.Text, nullable=True)
    migrated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
