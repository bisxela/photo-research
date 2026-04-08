from fastapi import APIRouter, HTTPException, Depends
import logging
import time
import re
from pathlib import Path
from typing import Optional

from app.models.schemas import TextSearchRequest, SimilarImageRequest, SearchResponse, ImageSearchResult, ImageResponse
from app.core.database import database
from app.core.clip_model import clip_encoder
from app.core.auth import get_current_user
from app.api.image import normalize_owner_id

logger = logging.getLogger(__name__)
router = APIRouter()


def build_image_urls(row) -> tuple[str, str]:
    file_ext = Path(row["filename"]).suffix.lower() or ".jpg"
    owner_prefix = row["owner_id"]
    return (
        f"/uploads/{owner_prefix}/{row['id']}_original{file_ext}",
        f"/uploads/{owner_prefix}/{row['id']}_thumbnail.jpg",
    )


def compute_ocr_match_score(query: str, ocr_text: Optional[str], filename: Optional[str] = None) -> float:
    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return 0.0

    combined_text = " ".join(filter(None, [(ocr_text or "").lower(), (filename or "").lower()]))
    if not combined_text:
        return 0.0

    score = 0.0
    if normalized_query in combined_text:
        score = 1.0

    tokens = [token for token in re.split(r"\s+", normalized_query) if token]
    if len(tokens) > 1:
        matched = sum(1 for token in tokens if token in combined_text)
        score = max(score, matched / len(tokens))

    return min(score, 1.0)


def build_ocr_excerpt(query: str, ocr_text: Optional[str]) -> Optional[str]:
    text = (ocr_text or "").strip()
    if not text:
        return None

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return text[:120]

    index = text.lower().find(normalized_query)
    if index < 0:
        return text[:120]

    start = max(0, index - 24)
    end = min(len(text), index + len(normalized_query) + 56)
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(text):
        excerpt = f"{excerpt}..."
    return excerpt


@router.post("/text", response_model=SearchResponse)
async def search_by_text(
    request: TextSearchRequest,
    current_user=Depends(get_current_user),
):
    """
    通过文本搜索图片
    
    使用Chinese CLIP将文本转换为向量，然后在数据库中进行相似度搜索
    """
    start_time = time.time()
    owner_id = normalize_owner_id(current_user["id"])
    
    try:
        # 1. 编码查询文本
        text_embedding = clip_encoder.encode_text(request.query)
        
        # 2. 将向量转换为pgvector字符串格式
        embedding_list = text_embedding.tolist()
        embedding_str = '[' + ','.join(str(x) for x in embedding_list) + ']'
        
        semantic_limit = min(max(request.top_k * 4, request.top_k), 100)
        semantic_query = """
            WITH ranked AS (
                SELECT 
                    i.id, i.owner_id, i.filename, i.original_path, i.thumbnail_path,
                    i.file_size, i.width, i.height, i.format, i.created_at,
                    i.checksum, i.ocr_text,
                    1 - (e.embedding <=> CAST(:embedding AS vector(512))) as similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(i.checksum, i.id::text)
                        ORDER BY 1 - (e.embedding <=> CAST(:embedding AS vector(512))) DESC, i.created_at ASC
                    ) AS dedupe_rank
                FROM image_embeddings e
                JOIN images i ON e.id = i.id
                WHERE i.owner_id = :owner_id
            )
            SELECT 
                id, owner_id, filename, original_path, thumbnail_path,
                file_size, width, height, format, created_at, similarity
            FROM ranked
            WHERE dedupe_rank = 1
            ORDER BY similarity DESC
            LIMIT :limit
        """

        semantic_rows = await database.fetch_all(
            semantic_query,
            {
                "embedding": embedding_str,
                "limit": semantic_limit,
                "owner_id": owner_id,
            }
        )

        ocr_pattern = f"%{request.query.strip().lower()}%"
        ocr_query = """
            SELECT
                i.id, i.owner_id, i.filename, i.original_path, i.thumbnail_path,
                i.file_size, i.width, i.height, i.format, i.created_at, i.ocr_text
            FROM images i
            WHERE i.owner_id = :owner_id
              AND COALESCE(i.ocr_text, '') <> ''
              AND (
                LOWER(i.ocr_text) LIKE :pattern
                OR LOWER(i.filename) LIKE :pattern
              )
            ORDER BY i.ocr_updated_at DESC NULLS LAST, i.created_at DESC
            LIMIT :limit
        """
        ocr_rows = await database.fetch_all(
            ocr_query,
            {
                "owner_id": owner_id,
                "pattern": ocr_pattern,
                "limit": semantic_limit,
            },
        )

        merged_results = {}

        for row in semantic_rows:
            semantic_score = max(0.0, min(float(row["similarity"]), 1.0))
            ocr_score = compute_ocr_match_score(request.query, row["ocr_text"], row["filename"])
            if request.search_type == "ocr":
                combined_score = max(ocr_score, semantic_score * 0.45 + ocr_score * 0.7)
                match_reason = "OCR 文本命中" if ocr_score > 0 else "语义候选补充"
            else:
                combined_score = min(1.0, semantic_score + ocr_score * 0.12)
                match_reason = "语义匹配 + OCR 文本命中" if ocr_score > 0 else "语义匹配"

            merged_results[str(row["id"])] = {
                "row": row,
                "score": combined_score,
                "ocr_score": ocr_score,
                "match_reason": match_reason,
            }

        for row in ocr_rows:
            image_id = str(row["id"])
            ocr_score = compute_ocr_match_score(request.query, row["ocr_text"], row["filename"])
            combined_score = ocr_score if request.search_type == "ocr" else min(1.0, 0.35 + ocr_score * 0.25)
            match_reason = "OCR 文本命中"
            existing = merged_results.get(image_id)
            if existing:
                if combined_score > existing["score"]:
                    existing["score"] = combined_score
                    existing["match_reason"] = match_reason
                existing["ocr_score"] = max(existing["ocr_score"], ocr_score)
                continue

            merged_results[image_id] = {
                "row": row,
                "score": combined_score,
                "ocr_score": ocr_score,
                "match_reason": match_reason,
            }

        ranked_results = sorted(
            merged_results.values(),
            key=lambda item: (item["score"], item["row"]["created_at"]),
            reverse=True,
        )[: request.top_k]

        search_results = []
        ocr_matched_count = 0
        for item in ranked_results:
            row = item["row"]
            original_url, thumbnail_url = build_image_urls(row)
            image_response = ImageResponse(
                id=row["id"],
                owner_id=row["owner_id"],
                filename=row["filename"],
                width=row["width"],
                height=row["height"],
                file_size=row["file_size"],
                format=row["format"],
                original_url=original_url,
                thumbnail_url=thumbnail_url,
                embedding_ready=True,
                created_at=row["created_at"],
            )

            if item["ocr_score"] > 0:
                ocr_matched_count += 1

            search_results.append(
                ImageSearchResult(
                    image=image_response,
                    similarity_score=max(0.0, min(item["score"], 1.0)),
                    match_reason=item["match_reason"],
                    ocr_text_excerpt=build_ocr_excerpt(request.query, row["ocr_text"]) if item["ocr_score"] > 0 else None,
                )
            )

        # 4. 记录搜索日志
        search_time_ms = int((time.time() - start_time) * 1000)
        try:
            await database.execute(
                """
                INSERT INTO search_logs (query_text, results_count, search_time_ms, owner_id, query_type)
                VALUES (:query, :count, :time, :owner_id, :query_type)
                """,
                {
                    "query": request.query,
                    "count": len(search_results),
                    "time": search_time_ms,
                    "owner_id": owner_id,
                    "query_type": request.search_type,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log search: {e}")
        
        return SearchResponse(
            query=request.query,
            owner_id=owner_id,
            results=search_results,
            total=len(search_results),
            search_time_ms=search_time_ms,
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/similar", response_model=SearchResponse)
async def search_similar_images(
    request: SimilarImageRequest,
    current_user=Depends(get_current_user),
):
    """
    搜索相似图片
    
    根据已有图片ID，找到数据库中相似的图片
    """
    start_time = time.time()
    owner_id = normalize_owner_id(current_user["id"])
    
    try:
        # 1. 获取查询图片的向量
        query = """
            SELECT e.embedding
            FROM image_embeddings e
            JOIN images i ON e.id = i.id
            WHERE e.id = :id AND i.owner_id = :owner_id
        """
        result = await database.fetch_one(
            query,
            {"id": str(request.image_id), "owner_id": owner_id},
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Image not found or not encoded yet")
        
        image_embedding = result["embedding"]
        
        # 2. 搜索相似图片（排除自己）
        query = """
            WITH ranked AS (
                SELECT 
                    i.id, i.owner_id, i.filename, i.original_path, i.thumbnail_path,
                    i.file_size, i.width, i.height, i.format, i.created_at,
                    i.checksum,
                    1 - (e.embedding <=> :embedding) as similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(i.checksum, i.id::text)
                        ORDER BY e.embedding <=> :embedding ASC, i.created_at ASC
                    ) AS dedupe_rank
                FROM image_embeddings e
                JOIN images i ON e.id = i.id
                WHERE e.id != :exclude_id AND i.owner_id = :owner_id
            )
            SELECT 
                id, owner_id, filename, original_path, thumbnail_path,
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
                "limit": request.top_k,
                "owner_id": owner_id,
            }
        )
        
        # 3. 构建响应
        search_results = []
        for row in results:
            original_url, thumbnail_url = build_image_urls(row)
            image_response = ImageResponse(
                id=row["id"],
                owner_id=row["owner_id"],
                filename=row["filename"],
                width=row["width"],
                height=row["height"],
                file_size=row["file_size"],
                format=row["format"],
                original_url=original_url,
                thumbnail_url=thumbnail_url,
                embedding_ready=True,
                created_at=row["created_at"]
            )
            
            search_results.append(ImageSearchResult(
                image=image_response,
                similarity_score=row["similarity"]
            ))
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            query=f"Similar to image {request.image_id}",
            owner_id=owner_id,
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
