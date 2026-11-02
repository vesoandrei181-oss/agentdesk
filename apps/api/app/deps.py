"""路由公共依赖：认证、工作区解析。"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import Membership, User, Workspace
from .security import decode_token


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少登录凭证")
    uid = decode_token(authorization.split(" ", 1)[1].strip())
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在")
    return user


def current_workspace(
    user: User = Depends(current_user),
    x_workspace: str | None = Header(default=None, alias="X-Workspace"),
    db: Session = Depends(get_db),
) -> Workspace:
    q = db.query(Workspace).join(Membership, Membership.workspace_id == Workspace.id).filter(
        Membership.user_id == user.id
    )
    if x_workspace and x_workspace.isdigit():
        ws = q.filter(Workspace.id == int(x_workspace)).first()
        if ws is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该工作区")
        return ws
    ws = q.order_by(Workspace.id).first()
    if ws is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "尚未加入任何工作区")
    return ws
