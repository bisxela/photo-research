# Photo Search 后端

这是 Photo Search 的 FastAPI 后端，负责图片上传、向量生成、文本搜图、相似图检索以及账号隔离。

## 技术栈

- FastAPI
- PostgreSQL 14 + pgvector
- Chinese CLIP
- Docker Compose

## 当前目录关系

后端与前端并列放在同一个仓库中：

```text
photo-search-frontend/
photo-search-backend/
```

## 当前功能

- 支持单图上传和批量上传
- 自动生成缩略图
- 相同文件可复用已有记录
- 使用 Chinese CLIP 编码图片
- 支持文本搜图
- 支持根据图片 ID 搜索相似图
- 通过 `/uploads` 暴露原图和缩略图
- 支持注册、登录与按账号隔离

## 运行前准备

- Docker
- Docker Compose
- 本地模型文件已放在 `models/chinese-clip-vit-base-patch16/`

`models/` 目录不会提交到 GitHub，需要你自己本地准备。

## 环境配置

先创建本地环境文件：

```bash
cp .env.example .env
```

默认配置已经适合本地 Docker Compose 开发。

## 本地启动

进入当前目录后执行：

```bash
docker compose up -d
```

查看状态：

```bash
docker compose ps
```

健康检查：

```bash
curl -s http://localhost:8000/health
```

接口文档：

```text
http://localhost:8000/docs
```

## GPU 模式

如果当前机器的 Docker 可以访问 NVIDIA GPU，可以使用 GPU 覆盖配置启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

然后检查日志中的设备信息：

```bash
docker compose logs -f backend | rg "Using device"
```

预期输出：

```text
Using device: cuda
```

## 暴露端口

- `8000`：FastAPI
- `5433`：主机侧 PostgreSQL 端口，容器内仍是 `5432`
- `9000`：MinIO API
- `9001`：MinIO Console

## 说明

- 上传文件保存在 Docker 卷挂载到的 `/app/data/uploads`
- 当前已支持批量上传和向量编码
- 搜索结果会按账号隔离
- 上传去重仍然基于 checksum
- 当前默认流程不依赖 MinIO 对象存储能力
- 默认使用 CPU
- GPU 模式由 `docker-compose.gpu.yml` 和 `Dockerfile.gpu` 提供

## 常用命令

启动：

```bash
docker compose up -d
```

停止：

```bash
docker compose down
```

查看后端日志：

```bash
docker compose logs -f backend
```
