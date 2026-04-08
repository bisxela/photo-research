from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from typing import List
from uuid import uuid4
from pathlib import Path
import logging
import shutil
import re

from app.models.schemas import (
    ImageCreate,
    ImageResponse,
    BatchUploadResponse,
    ImageOcrResponse,
    ImageOcrUpdateRequest,
)
from app.core.auth import get_current_user
from app.core.database import database
from app.core.clip_model import clip_encoder
from app.utils.image_processing import ImageProcessor
from app.utils.ocr import OcrProcessor
from app.utils.deduplication import compute_file_checksum
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
OWNER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")


def normalize_owner_id(owner_id: str) -> str:
    normalized = (owner_id or "").strip()
    if not OWNER_ID_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail="Invalid owner ID. Use 2-64 letters, numbers, hyphen, or underscore.",
        )
    return normalized


def build_image_response(row, embedding_ready: bool = False) -> ImageResponse:
    file_ext = Path(row["filename"]).suffix.lower()
    owner_prefix = row["owner_id"]

    return ImageResponse(
        id=row["id"],
        owner_id=row["owner_id"],
        filename=row["filename"],
        width=row["width"],
        height=row["height"],
        file_size=row["file_size"],
        format=row["format"],
        original_url=f"/uploads/{owner_prefix}/{row['id']}_original{file_ext}",
        thumbnail_url=f"/uploads/{owner_prefix}/{row['id']}_thumbnail.jpg",
        embedding_ready=embedding_ready,
        created_at=row["created_at"]
    )


def build_ocr_response(row) -> ImageOcrResponse:
    data = dict(row)
    text = (data.get("ocr_text") or "").strip()
    updated_at = data.get("ocr_updated_at")
    return ImageOcrResponse(
        image_id=data["id"],
        text=text,
        status="ready" if text else ("empty" if updated_at else "pending"),
        language=data.get("ocr_language"),
        source=data.get("ocr_source"),
        updated_at=updated_at,
    )


async def save_uploaded_image(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    owner_id: str,
) -> ImageResponse:
    """保存上传图片并安排后台编码。"""
    # 生成唯一ID
    image_id = str(uuid4())
    owner_id = normalize_owner_id(owner_id)
    
    # 保存文件
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.mpo']:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
    
    upload_dir = Path(settings.UPLOAD_DIR) / owner_id
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
            WHERE i.owner_id = :owner_id AND i.checksum = :checksum
            ORDER BY i.created_at ASC
            LIMIT 1
        """
        existing = await database.fetch_one(
            existing_query,
            {"checksum": checksum, "owner_id": owner_id},
        )
        if existing:
            original_path.unlink(missing_ok=True)
            logger.info(
                "Duplicate upload detected for owner %s file %s, reusing image %s",
                owner_id,
                file.filename,
                existing["id"],
            )
            return build_image_response(existing, embedding_ready=bool(existing["embedding_ready"]))
        
        # 获取图片信息
        image_info = ImageProcessor.get_image_info(original_path)
        
        # 创建缩略图
        ImageProcessor.create_thumbnail(original_path, thumbnail_path)
        
        # 保存到数据库
        query = """
            INSERT INTO images (
                id, owner_id, filename, original_path, thumbnail_path, file_size, width, height, format, checksum
            )
            VALUES (
                :id, :owner_id, :filename, :original_path, :thumbnail_path, :file_size, :width, :height, :format, :checksum
            )
            RETURNING *
        """
        values = {
            "id": image_id,
            "owner_id": owner_id,
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
        
        # 后台异步执行向量化与 OCR
        background_tasks.add_task(process_uploaded_image_task, image_id, original_path)
        
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
    file: UploadFile = File(..., description="要上传的图片文件"),
    current_user=Depends(get_current_user),
):
    """
    上传单张图片
    
    支持的格式: JPEG, PNG, GIF, BMP, WEBP, MPO
    最大文件大小: 10MB
    """
    return await save_uploaded_image(file, background_tasks, current_user["id"])


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user=Depends(get_current_user),
):
    """
    批量上传图片
    """
    results = []
    errors = []
    success_count = 0
    
    for file in files:
        try:
            result = await save_uploaded_image(file, background_tasks, current_user["id"])
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


@router.get("", response_model=List[ImageResponse])
async def list_images(current_user=Depends(get_current_user)):
    """
    获取当前账号的图片列表
    """
    query = """
        SELECT
            i.*,
            EXISTS(SELECT 1 FROM image_embeddings e WHERE e.id = i.id) AS embedding_ready
        FROM images i
        WHERE i.owner_id = :owner_id
        ORDER BY i.created_at DESC
    """
    rows = await database.fetch_all(
        query,
        {"owner_id": normalize_owner_id(current_user["id"])},
    )
    return [
        build_image_response(row, embedding_ready=bool(row["embedding_ready"]))
        for row in rows
    ]


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(image_id: str, current_user=Depends(get_current_user)):
    """
    获取图片信息
    """
    query = """
        SELECT
            i.*,
            EXISTS(SELECT 1 FROM image_embeddings e WHERE e.id = i.id) AS embedding_ready
        FROM images i
        WHERE i.id = :id AND i.owner_id = :owner_id
    """
    result = await database.fetch_one(
        query,
        {"id": image_id, "owner_id": normalize_owner_id(current_user["id"])},
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    
    file_ext = Path(result["filename"]).suffix

    return build_image_response(result, embedding_ready=bool(result["embedding_ready"]))


@router.get("/{image_id}/ocr", response_model=ImageOcrResponse)
async def get_image_ocr(image_id: str, current_user=Depends(get_current_user)):
    """
    获取当前图片的 OCR 结果
    """
    query = """
        SELECT id, ocr_text, ocr_source, ocr_language, ocr_updated_at
        FROM images
        WHERE id = :id AND owner_id = :owner_id
    """
    result = await database.fetch_one(
        query,
        {"id": image_id, "owner_id": normalize_owner_id(current_user["id"])},
    )

    if not result:
        raise HTTPException(status_code=404, detail="Image not found")

    return build_ocr_response(result)


@router.put("/{image_id}/ocr", response_model=ImageOcrResponse)
async def update_image_ocr(
    image_id: str,
    payload: ImageOcrUpdateRequest,
    current_user=Depends(get_current_user),
):
    """
    保存当前图片的 OCR 结果
    """
    owner_id = normalize_owner_id(current_user["id"])
    exists = await database.fetch_one(
        "SELECT id FROM images WHERE id = :id AND owner_id = :owner_id",
        {"id": image_id, "owner_id": owner_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Image not found")

    normalized_text = (payload.text or "").strip()
    query = """
        UPDATE images
        SET
            ocr_text = :ocr_text,
            ocr_source = :ocr_source,
            ocr_language = :ocr_language,
            ocr_updated_at = CURRENT_TIMESTAMP
        WHERE id = :id AND owner_id = :owner_id
        RETURNING id, ocr_text, ocr_source, ocr_language, ocr_updated_at
    """
    row = await database.fetch_one(
        query,
        {
            "id": image_id,
            "owner_id": owner_id,
            "ocr_text": normalized_text,
            "ocr_source": payload.source,
            "ocr_language": payload.language,
        },
    )

    return build_ocr_response(row)


@router.delete("/{image_id}")
async def delete_image(image_id: str, current_user=Depends(get_current_user)):
    """
    删除图片
    """
    # 查询图片信息
    query = "SELECT * FROM images WHERE id = :id AND owner_id = :owner_id"
    result = await database.fetch_one(
        query,
        {"id": image_id, "owner_id": normalize_owner_id(current_user["id"])},
    )
    
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


def process_uploaded_image_task(image_id: str, image_path: Path):
    """
    后台任务：编码图片向量并尝试提取 OCR 文本
    """
    import psycopg2

    conn = None
    cursor = None
    try:
        embedding = clip_encoder.encode_image(image_path)
        embedding_list = embedding.tolist()

        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO image_embeddings (id, embedding) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET embedding = %s",
            (image_id, embedding_list, embedding_list)
        )

        if OcrProcessor.is_available():
            ocr_text = OcrProcessor.extract_text(image_path, settings.OCR_LANGUAGES)
            cursor.execute(
                """
                UPDATE images
                SET
                    ocr_text = %s,
                    ocr_source = %s,
                    ocr_language = %s,
                    ocr_updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (ocr_text, "server_tesseract", settings.OCR_LANGUAGES, image_id),
            )

        conn.commit()
        logger.info("Image %s post-processing completed", image_id)
    except Exception as e:
        logger.error(f"Failed to encode image {image_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
