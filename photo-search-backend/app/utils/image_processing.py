from PIL import Image, ImageOps
from pathlib import Path
from typing import Tuple, Optional
import logging
import io

from app.config import settings

logger = logging.getLogger(__name__)


class ImageProcessor:
    """图片处理工具类"""
    
    SUPPORTED_FORMATS = {'JPEG', 'JPG', 'PNG', 'GIF', 'BMP', 'WEBP'}
    
    @staticmethod
    def validate_image(file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        验证图片文件
        
        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 检查文件存在
            if not file_path.exists():
                return False, f"File not found: {file_path}"
            
            # 检查文件大小
            file_size = file_path.stat().st_size
            if file_size > settings.MAX_FILE_SIZE:
                return False, f"File too large: {file_size} bytes (max: {settings.MAX_FILE_SIZE})"
            
            # 尝试打开图片
            with Image.open(file_path) as img:
                img_format = img.format
                if img_format not in ImageProcessor.SUPPORTED_FORMATS:
                    return False, f"Unsupported format: {img_format}"
                
                return True, None
                
        except Exception as e:
            return False, f"Invalid image file: {e}"
    
    @staticmethod
    def create_thumbnail(image_path: Path, thumbnail_path: Path, size: int = None) -> Tuple[int, int]:
        """
        创建缩略图
        
        Returns:
            (宽度, 高度)
        """
        if size is None:
            size = settings.THUMBNAIL_SIZE
        
        try:
            with Image.open(image_path) as img:
                # 转换为RGB（处理RGBA等模式）
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    else:
                        img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 创建缩略图
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                # 保存
                thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                
                return img.size
                
        except Exception as e:
            logger.error(f"Failed to create thumbnail for {image_path}: {e}")
            raise
    
    @staticmethod
    def get_image_info(image_path: Path) -> dict:
        """
        获取图片信息
        
        Returns:
            {
                'width': int,
                'height': int,
                'format': str,
                'file_size': int
            }
        """
        with Image.open(image_path) as img:
            return {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'file_size': image_path.stat().st_size
            }