"""用户注册、登录与账户信息"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import AccountUser
from backend.models.schemas import Response
from backend.utils.auth_deps import get_current_user
from backend.utils.security import create_access_token, get_password_hash, verify_password

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserInfo(BaseModel):
    id: int
    username: str
    email: str | None = None


@router.post("/register", response_model=Response)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(AccountUser).filter(AccountUser.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if body.email and db.query(AccountUser).filter(AccountUser.email == body.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    user = AccountUser(
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return Response(code=200, message="注册成功", data={"id": user.id, "username": user.username})


@router.post("/login", response_model=Response)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AccountUser).filter(AccountUser.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已禁用")

    token = create_access_token({"sub": user.username})
    return Response(
        code=200,
        data=TokenResponse(access_token=token, username=user.username).model_dump(),
    )


@router.get("/me", response_model=Response)
async def get_me(current_user: AccountUser = Depends(get_current_user)):
    return Response(
        code=200,
        data=UserInfo(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
        ).model_dump(),
    )


@router.post("/logout", response_model=Response)
async def logout():
    """JWT 无状态，客户端删除 Token 即可"""
    return Response(code=200, message="已退出登录")
