"""认证相关路由：登录、管理员创建用户"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_token, verify_admin_key

router = APIRouter()


# ========== 登录 ==========

class LoginRequest(BaseModel):
    phone: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """手机号 + 密码登录"""
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if not user.password_hash:
        raise HTTPException(status_code=401, detail="该账号未设置密码")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")

    token = create_token(user.id)
    return LoginResponse(
        token=token,
        user={
            "id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "profile_completed": user.profile_completed or False,
        },
    )


# ========== 管理员接口 ==========

class AdminCreateUserRequest(BaseModel):
    phone: str
    password: str


class AdminCreateUserResponse(BaseModel):
    user_id: str
    phone: str


admin_router = APIRouter()


@admin_router.post("/user", response_model=AdminCreateUserResponse)
def admin_create_user(
    req: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员创建用户"""
    # 检查手机号是否已存在
    existing = db.query(User).filter(User.phone == req.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已注册")

    user = User(
        phone=req.phone,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AdminCreateUserResponse(user_id=user.id, phone=user.phone)
