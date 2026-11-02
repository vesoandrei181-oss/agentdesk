"""认证与工作区。令牌走 Bearer，前端存 localStorage。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import AuditLog, Membership, User, Workspace
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=40)
    workspace_name: str = "我的团队"


def user_payload(db: Session, user: User) -> dict:
    ws = (
        db.query(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .filter(Membership.user_id == user.id)
        .all()
    )
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "title": user.title,
        "avatar_hue": user.avatar_hue,
        "workspaces": [{"id": w.id, "name": w.name, "slug": w.slug, "plan": w.plan} for w in ws],
    }


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码不正确")
    db.add(AuditLog(workspace_id=0, user_id=user.id, action="login", detail={"email": user.email}))
    db.commit()
    return {"token": create_token(user.id), "user": user_payload(db, user)}


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password), title="成员")
    db.add(user)
    db.flush()
    slug = f"ws-{user.id}"
    ws = Workspace(name=body.workspace_name, slug=slug)
    db.add(ws)
    db.flush()
    db.add(Membership(user_id=user.id, workspace_id=ws.id, role="owner"))
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "user": user_payload(db, user)}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_payload(db, user)
