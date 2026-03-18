#!/bin/bash

# 等待MinIO启动
sleep 10

# 配置mc客户端
mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-fish123}

# 创建存储桶
mc mb -p local/photos-original
mc mb -p local/photos-thumbnail

# 设置公开访问策略（可选，生产环境建议关闭）
mc policy set download local/photos-original
mc policy set download local/photos-thumbnail

echo "Buckets created successfully"