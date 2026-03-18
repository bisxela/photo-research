import torch
from transformers import ChineseCLIPProcessor, ChineseCLIPModel, ChineseCLIPFeatureExtractor, BertTokenizer
from PIL import Image
import numpy as np
from typing import Union, List
import logging
from pathlib import Path
import os

from app.config import settings

logger = logging.getLogger(__name__)


class ChineseCLIPEncoder:
    """Chinese CLIP 编码器"""
    
    _instance = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_path = settings.CLIP_MODEL_PATH
        self.model_name = settings.CLIP_MODEL_NAME
        
        logger.info(f"Loading Chinese CLIP model from {self.model_path}")
        logger.info(f"Using device: {self.device}")
        
        try:
            # 尝试从本地路径加载
            if Path(self.model_path).exists():
                logger.info(f"Loading model from local path: {self.model_path}")
                
                # 尝试加载模型
                self.model = ChineseCLIPModel.from_pretrained(self.model_path)
                
                # 尝试加载processor，使用多种方法
                try:
                    # 方法1：尝试使用ChineseCLIPProcessor
                    self.processor = ChineseCLIPProcessor.from_pretrained(self.model_path)
                    logger.info("Loaded processor using ChineseCLIPProcessor")
                except Exception as e1:
                    logger.warning(f"Failed to load ChineseCLIPProcessor: {e1}")
                    try:
                        # 方法2：分别加载feature extractor和tokenizer
                        feature_extractor_path = self.model_path
                        tokenizer_path = self.model_path
                        
                        # 检查必要的文件是否存在
                        vocab_file = os.path.join(tokenizer_path, "vocab.txt")
                        if not os.path.exists(vocab_file):
                            raise FileNotFoundError(f"Vocabulary file not found: {vocab_file}")
                        
                        # 加载特征提取器
                        self.feature_extractor = ChineseCLIPFeatureExtractor.from_pretrained(feature_extractor_path)
                        
                        # 加载分词器，直接实例化
                        logger.info(f"Loading tokenizer from vocab file: {vocab_file}")
                        logger.info(f"File exists: {os.path.exists(vocab_file)}")
                        
                        # 读取词汇表内容的前几行进行验证
                        try:
                            with open(vocab_file, 'r', encoding='utf-8') as f:
                                vocab_lines = [next(f).strip() for _ in range(5)]
                            logger.info(f"First 5 vocab items: {vocab_lines}")
                        except Exception as e:
                            logger.warning(f"Could not read vocab file: {e}")
                        
                        self.tokenizer = BertTokenizer(
                            vocab_file=vocab_file,
                            do_lower_case=False,
                            do_basic_tokenize=True,
                            never_split=None,
                            unk_token="[UNK]",
                            sep_token="[SEP]",
                            pad_token="[PAD]",
                            cls_token="[CLS]",
                            mask_token="[MASK]",
                            tokenize_chinese_chars=True,
                            strip_accents=None,
                            model_max_length=512
                        )
                        
                        logger.info("Loaded processor using ChineseCLIPFeatureExtractor + BertTokenizer")
                        
                        # 创建processor模拟对象
                        class CustomProcessor:
                            def __init__(self, feature_extractor, tokenizer):
                                self.feature_extractor = feature_extractor
                                self.tokenizer = tokenizer
                                
                            def __call__(self, *args, **kwargs):
                                # 根据输入类型调用相应的方法
                                if 'images' in kwargs or (len(args) > 0 and isinstance(args[0], (list, Image.Image))):
                                    return self.feature_extractor(*args, **kwargs)
                                else:
                                    return self.tokenizer(*args, **kwargs)
                                    
                            def __getattr__(self, name):
                                # 委托给feature_extractor或tokenizer
                                if hasattr(self.feature_extractor, name):
                                    return getattr(self.feature_extractor, name)
                                elif hasattr(self.tokenizer, name):
                                    return getattr(self.tokenizer, name)
                                else:
                                    raise AttributeError(f"'CustomProcessor' object has no attribute '{name}'")
                        
                        self.processor = CustomProcessor(self.feature_extractor, self.tokenizer)
                        
                    except Exception as e2:
                        logger.error(f"Failed to load processor with fallback method: {e2}")
                        raise
            else:
                # 从HuggingFace下载并保存到本地
                logger.warning(f"Local model not found, downloading from {self.model_name}")
                self.processor = ChineseCLIPProcessor.from_pretrained(self.model_name)
                self.model = ChineseCLIPModel.from_pretrained(self.model_name)
                # 保存到本地路径供后续使用
                logger.info(f"Saving model to local path: {self.model_path}")
                Path(self.model_path).mkdir(parents=True, exist_ok=True)
                self.processor.save_pretrained(self.model_path)
                self.model.save_pretrained(self.model_path)
                logger.info(f"Model saved successfully")
            
            self.model.to(self.device)
            self.model.eval()
            
            self._initialized = True
            logger.info("Chinese CLIP model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def encode_image(self, image_path: Union[str, Path]) -> np.ndarray:
        """
        编码单张图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            512维向量 (numpy array)
        """
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                # 归一化
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy().flatten()
            
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            raise
    
    def encode_images_batch(self, image_paths: List[Union[str, Path]], batch_size: int = 8) -> np.ndarray:
        """
        批量编码图片
        
        Args:
            image_paths: 图片路径列表
            batch_size: 批次大小
            
        Returns:
            N x 512 矩阵
        """
        all_features = []
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            batch_images = []
            
            for path in batch_paths:
                try:
                    img = Image.open(path).convert("RGB")
                    batch_images.append(img)
                except Exception as e:
                    logger.error(f"Failed to load image {path}: {e}")
                    continue
            
            if not batch_images:
                continue
            
            inputs = self.processor(images=batch_images, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            all_features.append(image_features.cpu().numpy())
        
        if not all_features:
            return np.array([])
        
        return np.vstack(all_features)
    
    def encode_text(self, text: str) -> np.ndarray:
        """
        编码文本
        
        Args:
            text: 输入文本
            
        Returns:
            512维向量
        """
        inputs = self.processor(text=[text], return_tensors="pt", padding=True, truncation=True, max_length=77)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
        return text_features.cpu().numpy().flatten()
    
    def encode_texts_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        批量编码文本
        """
        all_features = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            inputs = self.processor(text=batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=77)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            all_features.append(text_features.cpu().numpy())
        
        return np.vstack(all_features) if all_features else np.array([])


# 全局编码器实例
clip_encoder = ChineseCLIPEncoder()