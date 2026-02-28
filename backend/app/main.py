from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api import router

# 创建数据库表（仅 SQLite 模式，PostgreSQL 由 Alembic 管理）
if "sqlite" in settings.database_url:
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="回忆录 API",
    description="帮助老年人记录人生故事的AI对话服务",
    version="0.1.0"
)

# 配置跨域（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://storyofme.cn",
        "https://www.storyofme.cn",
        "http://localhost:8080",  # 本地开发
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"message": "回忆录 API 服务正在运行", "version": "0.1.0"}


@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "healthy"}
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
