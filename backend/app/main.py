from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api import router

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="回忆录 API",
    description="帮助老年人记录人生故事的AI对话服务",
    version="0.1.0"
)

# 配置跨域（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
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
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
