from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 数据库配置
    POSTGRES_USER: str = "photo_search"
    POSTGRES_PASSWORD: str = "fish"
    POSTGRES_DB: str = "photo_search_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    
    # MinIO配置
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "fish1234"
    MINIO_HOST: str = "minio"
    MINIO_PORT: int = 9000
    
    # CLIP模型配置
    CLIP_MODEL_NAME: str = "OFA-Sys/chinese-clip-vit-base-patch16"
    CLIP_MODEL_PATH: str = "/app/models/chinese-clip-vit-base-patch16"
    
    # 应用配置
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    UPLOAD_DIR: str = "/app/data/uploads"
    THUMBNAIL_SIZE: int = 200
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def MINIO_ENDPOINT(self) -> str:
        """MinIO服务端点"""
        return f"{self.MINIO_HOST}:{self.MINIO_PORT}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()