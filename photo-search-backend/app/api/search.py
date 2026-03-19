from fastapi import APIRouter, HTTPException
from typing import List
import logging
import time

from app.models.schemas import TextSearchRequest, SimilarImageRequest, SearchResponse, ImageSearchResult, ImageResponse
from app.core.database import database
from app.core.clip_model import clip_encoder

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/text", response_model=SearchResponse)
async def search_by_text(request: TextSearchRequest):
    """
    通过文本搜索图片
    
    使用Chinese CLIP将文本转换为向量，然后在数据库中进行相似度搜索
    """
    start_time = time.time()
    
    try:
        # 1. 编码查询文本
        text_embedding = clip_encoder.encode_text(request.query)
        
        # 2. 将向量转换为pgvector字符串格式
        embedding_list = text_embedding.tolist()
        embedding_str = '[' + ','.join(str(x) for x in embedding_list) + ']'
        
        # 3. 执行向量相似度搜索
        query = """
            WITH ranked AS (
                SELECT 
                    i.id, i.filename, i.original_path, i.thumbnail_path,
                    i.file_size, i.width, i.height, i.format, i.created_at,
                    i.checksum,
                    1 - (e.embedding <=> CAST(:embedding AS vector(512))) as similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(i.checksum, i.id::text)
                        ORDER BY 1 - (e.embedding <=> CAST(:embedding AS vector(512))) DESC, i.created_at ASC
                    ) AS dedupe_rank
                FROM image_embeddings e
                JOIN images i ON e.id = i.id
            )
            SELECT 
                id, filename, original_path, thumbnail_path,
                file_size, width, height, format, created_at, similarity
            FROM ranked
            WHERE dedupe_rank = 1
            ORDER BY similarity DESC
            LIMIT :limit
        """
        
        results = await database.fetch_all(
            query, 
            {
                "embedding": embedding_str,
                "limit": request.top_k
            }
        )
        
        # 3. 构建响应
        search_results = []
        for row in results:
            file_ext = row["filename"].split('.')[-1] if '.' in row["filename"] else 'jpg'
            
            image_response = ImageResponse(
                id=row["id"],
                filename=row["filename"],
                width=row["width"],
                height=row["height"],
                file_size=row["file_size"],
                format=row["format"],
                original_url=f"/uploads/{row['id']}_original.{file_ext}",
                thumbnail_url=f"/uploads/{row['id']}_thumbnail.jpg",
                created_at=row["created_at"]
            )
            
            search_results.append(ImageSearchResult(
                image=image_response,
                similarity_score=row["similarity"]
            ))
        
        # 4. 记录搜索日志
        search_time_ms = int((time.time() - start_time) * 1000)
        try:
            await database.execute(
                "INSERT INTO search_logs (query_text, results_count, search_time_ms) VALUES (:query, :count, :time)",
                {"query": request.query, "count": len(search_results), "time": search_time_ms}
            )
        except Exception as e:
            logger.warning(f"Failed to log search: {e}")
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total=len(search_results),
            search_time_ms=search_time_ms
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/similar", response_model=SearchResponse)
async def search_similar_images(request: SimilarImageRequest):
    """
    搜索相似图片
    
    根据已有图片ID，找到数据库中相似的图片
    """
    start_time = time.time()
    
    try:
        # 1. 获取查询图片的向量
        query = "SELECT embedding FROM image_embeddings WHERE id = :id"
        result = await database.fetch_one(query, {"id": str(request.image_id)})
        
        if not result:
            raise HTTPException(status_code=404, detail="Image not found or not encoded yet")
        
        image_embedding = result["embedding"]
        
        # 2. 搜索相似图片（排除自己）
        query = """
            WITH ranked AS (
                SELECT 
                    i.id, i.filename, i.original_path, i.thumbnail_path,
                    i.file_size, i.width, i.height, i.format, i.created_at,
                    i.checksum,
                    1 - (e.embedding <=> :embedding) as similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(i.checksum, i.id::text)
                        ORDER BY e.embedding <=> :embedding ASC, i.created_at ASC
                    ) AS dedupe_rank
                FROM image_embeddings e
                JOIN images i ON e.id = i.id
                WHERE e.id != :exclude_id
            )
            SELECT 
                id, filename, original_path, thumbnail_path,
                file_size, width, height, format, created_at, similarity
            FROM ranked
            WHERE dedupe_rank = 1
            ORDER BY similarity DESC
            LIMIT :limit
        """
        
        results = await database.fetch_all(
            query,
            {
                "embedding": image_embedding,
                "exclude_id": str(request.image_id),
                "limit": request.top_k
            }
        )
        
        # 3. 构建响应
        search_results = []
        for row in results:
            file_ext = row["filename"].split('.')[-1] if '.' in row["filename"] else 'jpg'
            
            image_response = ImageResponse(
                id=row["id"],
                filename=row["filename"],
                width=row["width"],
                height=row["height"],
                file_size=row["file_size"],
                format=row["format"],
                original_url=f"/uploads/{row['id']}_original.{file_ext}",
                thumbnail_url=f"/uploads/{row['id']}_thumbnail.jpg",
                created_at=row["created_at"]
            )
            
            search_results.append(ImageSearchResult(
                image=image_response,
                similarity_score=row["similarity"]
            ))
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            query=f"Similar to image {request.image_id}",
            results=search_results,
            total=len(search_results),
            search_time_ms=search_time_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similar image search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/stats")
async def get_search_stats():
    """
    获取搜索统计信息
    """
    try:
        # 总搜索次数
        total_searches = await database.fetch_one("SELECT COUNT(*) as count FROM search_logs")
        
        # 今日搜索次数
        today_searches = await database.fetch_one(
            "SELECT COUNT(*) as count FROM search_logs WHERE created_at >= CURRENT_DATE"
        )
        
        # 平均搜索时间
        avg_time = await database.fetch_one(
            "SELECT AVG(search_time_ms) as avg_time FROM search_logs"
        )
        
        # 热门查询
        popular_queries = await database.fetch_all(
            """
            SELECT query_text, COUNT(*) as count 
            FROM search_logs 
            GROUP BY query_text 
            ORDER BY count DESC 
            LIMIT 10
            """
        )
        
        return {
            "total_searches": total_searches["count"] if total_searches else 0,
            "today_searches": today_searches["count"] if today_searches else 0,
            "avg_search_time_ms": round(avg_time["avg_time"], 2) if avg_time and avg_time["avg_time"] else 0,
            "popular_queries": [
                {"query": row["query_text"], "count": row["count"]} 
                for row in (popular_queries or [])
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
