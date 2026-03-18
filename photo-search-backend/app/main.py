from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.api.router import api_router
from app.config import settings
from app.core.database import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await database.connect()
    print("✅ Database connected")
    yield
    # 关闭时执行
    await database.disconnect()
    print("❌ Database disconnected")


app = FastAPI(
    title="Photo Search API",
    description="基于Chinese CLIP的多模态图片搜索服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api/v1")

# 静态文件服务
app.mount("/uploads", StaticFiles(directory="/app/data/uploads"), name="uploads")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "services": {
            "database": "connected" if database.is_connected else "disconnected",
            "model": "loaded"  # 后续可以添加模型状态检查
        }
    }


@app.get("/")
async def root():
    """根路径重定向到文档"""
    return {
        "message": "Photo Search API",
        "docs": "/docs",
        "health": "/health"
    }