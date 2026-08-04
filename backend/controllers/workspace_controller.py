"""Workspace and membership endpoints for local/multi-tenant deployments."""
import re
import uuid

from flask import Blueprint, g, request

from models import db, Membership, User, Workspace
from utils.response import bad_request, error_response, success_response


workspace_bp = Blueprint('workspaces', __name__, url_prefix='/api/workspaces')


def _workspace_dict(workspace, role=None):
    return {
        'id': workspace.id,
        'name': workspace.name,
        'slug': workspace.slug,
        'owner_user_id': workspace.owner_user_id,
        'role': role,
    }


@workspace_bp.get('')
def list_workspaces():
    rows = (
        db.session.query(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .filter(Membership.user_id == g.current_user_id)
        .order_by(Workspace.created_at)
        .all()
    )
    return success_response({'workspaces': [_workspace_dict(w, role) for w, role in rows]})


@workspace_bp.post('')
def create_workspace():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    slug = str(data.get('slug') or '').strip().lower()
    if not name or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,98}[a-z0-9]', slug):
        return bad_request('name and a 3-100 character lowercase slug are required')
    if Workspace.query.filter_by(slug=slug).first():
        return error_response('WORKSPACE_SLUG_EXISTS', 'Workspace slug already exists', 409)
    workspace = Workspace(name=name, slug=slug, owner_user_id=g.current_user_id)
    db.session.add(workspace)
    db.session.flush()
    db.session.add(Membership(
        workspace_id=workspace.id, user_id=g.current_user_id, role='owner'
    ))
    db.session.commit()
    return success_response(_workspace_dict(workspace, 'owner'), status_code=201)


@workspace_bp.get('/<workspace_id>/members')
def list_members(workspace_id):
    if workspace_id != g.current_workspace_id:
        return error_response('WORKSPACE_ACCESS_DENIED', 'Workspace access denied', 403)
    members = Membership.query.filter_by(workspace_id=workspace_id).all()
    return success_response({'members': [member.to_dict() for member in members]})


@workspace_bp.post('/<workspace_id>/members')
def upsert_member(workspace_id):
    if workspace_id != g.current_workspace_id or g.current_workspace_role != 'owner':
        return error_response('OWNER_REQUIRED', 'Workspace owner permission required', 403)
    data = request.get_json(silent=True) or {}
    email = str(data.get('email') or '').strip().lower()
    role = str(data.get('role') or 'viewer').strip().lower()
    if not email or role not in {'owner', 'editor', 'viewer'}:
        return bad_request('email and a valid role are required')
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(id=str(uuid.uuid4()), email=email, display_name=data.get('display_name') or email)
        db.session.add(user)
        db.session.flush()
    member = Membership.query.filter_by(workspace_id=workspace_id, user_id=user.id).first()
    if member:
        member.role = role
    else:
        member = Membership(workspace_id=workspace_id, user_id=user.id, role=role)
        db.session.add(member)
    db.session.commit()
    return success_response(member.to_dict())
