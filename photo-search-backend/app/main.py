from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.api.router import api_router
from app.config import settings
from app.core.database import database
from app.utils.deduplication import compute_file_checksum

logger = logging.getLogger(__name__)


async def run_startup_migrations():
    await database.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS checksum VARCHAR(64)")
    await database.execute("DROP INDEX IF EXISTS idx_images_checksum_unique")
    await database.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_images_checksum
        ON images (checksum)
        """
    )


async def backfill_missing_checksums():
    rows = await database.fetch_all(
        """
        SELECT id, original_path
        FROM images
        WHERE checksum IS NULL
        ORDER BY created_at ASC
        """
    )

    if not rows:
        return

    logger.info("Backfilling checksums for %d images", len(rows))

    for row in rows:
        image_path = Path(row["original_path"])
        if not image_path.exists():
            logger.warning("Cannot backfill checksum, file missing: %s", image_path)
            continue

        checksum = compute_file_checksum(image_path)
        await database.execute(
            "UPDATE images SET checksum = :checksum WHERE id = :id",
            {"checksum": checksum, "id": row["id"]},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await database.connect()
    await run_startup_migrations()
    await backfill_missing_checksums()
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
