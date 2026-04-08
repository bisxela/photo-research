-- 启用pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username VARCHAR(32) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 图片元数据表
CREATE TABLE IF NOT EXISTS images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id VARCHAR(64) NOT NULL DEFAULT 'legacy-shared',
    filename VARCHAR(255) NOT NULL,
    original_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    checksum VARCHAR(64),
    ocr_text TEXT,
    ocr_source VARCHAR(64),
    ocr_language VARCHAR(64),
    ocr_updated_at TIMESTAMP,
    file_size BIGINT,
    width INTEGER,
    height INTEGER,
    format VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 向量存储表
CREATE TABLE IF NOT EXISTS image_embeddings (
    id UUID PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
    embedding vector(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 搜索记录表（用于分析）
CREATE TABLE IF NOT EXISTS search_logs (
    id SERIAL PRIMARY KEY,
    owner_id VARCHAR(64),
    query_text TEXT,
    query_type VARCHAR(50) DEFAULT 'text',
    results_count INTEGER,
    search_time_ms INTEGER,
    user_ip INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建向量索引（IVFFlat索引，适合中等规模数据）
CREATE INDEX IF NOT EXISTS idx_image_embeddings_vector 
ON image_embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- 创建普通索引优化查询
CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at);
CREATE INDEX IF NOT EXISTS idx_images_filename ON images(filename);
CREATE INDEX IF NOT EXISTS idx_images_checksum ON images(checksum);
CREATE INDEX IF NOT EXISTS idx_images_owner_id ON images(owner_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 添加注释
COMMENT ON TABLE images IS '存储图片元数据信息';
COMMENT ON TABLE image_embeddings IS '存储图片的CLIP向量表示';
COMMENT ON TABLE search_logs IS '记录搜索查询日志用于分析';
