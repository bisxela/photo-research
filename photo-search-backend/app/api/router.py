from fastapi import APIRouter

from app.api import image, search

api_router = APIRouter()

# 注册子路由
api_router.include_router(image.router, prefix="/images", tags=["Images"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])