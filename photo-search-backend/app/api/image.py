from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List
from uuid import uuid4
from pathlib import Path
import logging
import shutil

from app.models.schemas import ImageCreate, ImageResponse, BatchUploadResponse
from app.core.database import database
from app.core.clip_model import clip_encoder
from app.utils.image_processing import ImageProcessor
from app.utils.deduplication import compute_file_checksum
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def build_image_response(row, embedding_ready: bool = False) -> ImageResponse:
    file_ext = Path(row["filename"]).suffix.lower()

    return ImageResponse(
        id=row["id"],
        filename=row["filename"],
        width=row["width"],
        height=row["height"],
        file_size=row["file_size"],
        format=row["format"],
        original_url=f"/uploads/{row['id']}_original{file_ext}",
        thumbnail_url=f"/uploads/{row['id']}_thumbnail.jpg",
        embedding_ready=embedding_ready,
        created_at=row["created_at"]
    )


async def save_uploaded_image(file: UploadFile, background_tasks: BackgroundTasks) -> ImageResponse:
    """保存上传图片并安排后台编码。"""
    # 生成唯一ID
    image_id = str(uuid4())
    
    # 保存文件
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.mpo']:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
    
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    original_path = upload_dir / f"{image_id}_original{file_ext}"
    thumbnail_path = upload_dir / f"{image_id}_thumbnail.jpg"
    
    try:
        # 保存原始文件
        with open(original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 验证图片
        is_valid, error_msg = ImageProcessor.validate_image(original_path)
        if not is_valid:
            original_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=error_msg)

        checksum = compute_file_checksum(original_path)

        existing_query = """
            SELECT
                i.*,
                EXISTS(SELECT 1 FROM image_embeddings e WHERE e.id = i.id) AS embedding_ready
            FROM images i
            WHERE i.checksum = :checksum
            ORDER BY i.created_at ASC
            LIMIT 1
        """
        existing = await database.fetch_one(existing_query, {"checksum": checksum})
        if existing:
            original_path.unlink(missing_ok=True)
            logger.info("Duplicate upload detected for %s, reusing image %s", file.filename, existing["id"])
            return build_image_response(existing, embedding_ready=bool(existing["embedding_ready"]))
        
        # 获取图片信息
        image_info = ImageProcessor.get_image_info(original_path)
        
        # 创建缩略图
        ImageProcessor.create_thumbnail(original_path, thumbnail_path)
        
        # 保存到数据库
        query = """
            INSERT INTO images (id, filename, original_path, thumbnail_path, file_size, width, height, format, checksum)
            VALUES (:id, :filename, :original_path, :thumbnail_path, :file_size, :width, :height, :format, :checksum)
            RETURNING *
        """
        values = {
            "id": image_id,
            "filename": file.filename,
            "original_path": str(original_path),
            "thumbnail_path": str(thumbnail_path),
            "file_size": image_info['file_size'],
            "width": image_info['width'],
            "height": image_info['height'],
            "format": image_info['format'],
            "checksum": checksum,
        }
        
        result = await database.fetch_one(query, values)
        
        # 后台异步编码图片向量
        background_tasks.add_task(encode_image_task, image_id, original_path)
        
        return build_image_response(result, embedding_ready=False)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload image: {e}")
        # 清理文件
        original_path.unlink(missing_ok=True)
        thumbnail_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload", response_model=ImageResponse)
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="要上传的图片文件")
):
    """
    上传单张图片
    
    支持的格式: JPEG, PNG, GIF, BMP, WEBP, MPO
    最大文件大小: 10MB
    """
    return await save_uploaded_image(file, background_tasks)


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """
    批量上传图片
    """
    results = []
    errors = []
    success_count = 0
    
    for file in files:
        try:
            result = await save_uploaded_image(file, background_tasks)
            results.append(result)
            success_count += 1
        except HTTPException as e:
            errors.append(f"{file.filename}: {e.detail}")
        except Exception as e:
            errors.append(f"{file.filename}: {str(e)}")
    
    return BatchUploadResponse(
        success_count=success_count,
        failed_count=len(errors),
        images=results,
        errors=errors
    )


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(image_id: str):
    """
    获取图片信息
    """
    query = """
        SELECT
            i.*,
            EXISTS(SELECT 1 FROM image_embeddings e WHERE e.id = i.id) AS embedding_ready
        FROM images i
        WHERE i.id = :id
    """
    result = await database.fetch_one(query, {"id": image_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    
    file_ext = Path(result["filename"]).suffix
    
    return build_image_response(result, embedding_ready=bool(result["embedding_ready"]))


@router.delete("/{image_id}")
async def delete_image(image_id: str):
    """
    删除图片
    """
    # 查询图片信息
    query = "SELECT * FROM images WHERE id = :id"
    result = await database.fetch_one(query, {"id": image_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        # 删除向量
        await database.execute("DELETE FROM image_embeddings WHERE id = :id", {"id": image_id})
        
        # 删除数据库记录
        await database.execute("DELETE FROM images WHERE id = :id", {"id": image_id})
        
        # 删除文件
        original_path = Path(result["original_path"])
        thumbnail_path = Path(result["thumbnail_path"])
        original_path.unlink(missing_ok=True)
        thumbnail_path.unlink(missing_ok=True)
        
        return {"status": "success", "message": "Image deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


def encode_image_task(image_id: str, image_path: Path):
    """
    后台任务：编码图片向量
    """
    try:
        # 编码图片
        embedding = clip_encoder.encode_image(image_path)
        
        # 转换为列表以便存储
        embedding_list = embedding.tolist()
        
        # 保存到数据库（使用同步连接）
        import psycopg2
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO image_embeddings (id, embedding) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET embedding = %s",
            (image_id, embedding_list, embedding_list)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Image {image_id} encoded successfully")
        
    except Exception as e:
        logger.error(f"Failed to encode image {image_id}: {e}")
