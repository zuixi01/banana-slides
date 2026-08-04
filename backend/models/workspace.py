"""Local-first users, workspaces, and role memberships."""
import uuid
from datetime import datetime

from . import db


DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), nullable=False, unique=True)
    display_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Workspace(db.Model):
    __tablename__ = "workspaces"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    owner_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    owner = db.relationship("User", foreign_keys=[owner_user_id])
    memberships = db.relationship(
        "Membership", back_populates="workspace", cascade="all, delete-orphan"
    )


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "user_id", name="uq_membership_workspace_user"),
        db.CheckConstraint("role IN ('owner','editor','viewer')", name="ck_membership_role"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = db.Column(
        db.String(36), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = db.Column(db.String(20), nullable=False, default="viewer")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    workspace = db.relationship("Workspace", back_populates="memberships")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "role": self.role,
            "email": self.user.email if self.user else None,
            "display_name": self.user.display_name if self.user else None,
        }
