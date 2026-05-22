"""SQLAlchemy 数据库连接与会话管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.config import DATABASE_URL, DATABASE_PATH

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：请求级数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表"""
    from backend.models import user as _user  # noqa: F401
    from backend.models import db_models as _db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
