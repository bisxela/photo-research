import asyncpg
from databases import Database
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self._database: Optional[Database] = None
    
    @property
    def database(self) -> Database:
        if self._database is None:
            self._database = Database(settings.DATABASE_URL)
        return self._database
    
    async def connect(self):
        """连接数据库"""
        import asyncio
        max_retries = 5
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                await self.database.connect()
                logger.info("Database connected successfully")
                return
            except Exception as e:
                logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                    raise
                delay = base_delay * (2 ** attempt)
                logger.info(f"Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)
    
    async def disconnect(self):
        """断开数据库连接"""
        if self._database:
            await self.database.disconnect()
            logger.info("Database disconnected")
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._database is not None and self._database.is_connected
    
    async def fetch_one(self, query: str, *args):
        """查询单条记录"""
        return await self.database.fetch_one(query, *args)
    
    async def fetch_all(self, query: str, *args):
        """查询多条记录"""
        return await self.database.fetch_all(query, *args)
    
    async def execute(self, query: str, *args):
        """执行SQL"""
        return await self.database.execute(query, *args)
    
    async def execute_many(self, query: str, values):
        """批量执行"""
        return await self.database.execute_many(query, values)


# 全局数据库实例
database = DatabaseManager()