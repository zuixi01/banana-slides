"""Immutable outline snapshots for review, refinement and rollback."""
import json
import uuid
from datetime import datetime

from . import db


class OutlineVersion(db.Model):
    __tablename__ = 'outline_versions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    parent_version_id = db.Column(db.String(36), db.ForeignKey('outline_versions.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='draft')
    instruction = db.Column(db.Text, nullable=True)
    outline_json = db.Column(db.Text, nullable=False)
    diff_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('project_id', 'version_number', name='uq_outline_version_project_number'),
    )

    def outline(self):
        return json.loads(self.outline_json or '[]')

    def diff(self):
        return json.loads(self.diff_json or '{}')

    def to_dict(self, include_outline=True):
        data = {
            'id': self.id,
            'project_id': self.project_id,
            'version': self.version_number,
            'parent_version_id': self.parent_version_id,
            'status': self.status,
            'instruction': self.instruction,
            'diff': self.diff(),
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'confirmed_at': self.confirmed_at.isoformat() + 'Z' if self.confirmed_at else None,
        }
        if include_outline:
            data['outline'] = self.outline()
        return data
