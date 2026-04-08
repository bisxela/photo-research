# Photo Search

Photo Search 是一个基于 Chinese CLIP 的图片语义检索 Web Demo。

它已经完成了从“上传图片”到“文本搜图 / 以图搜图”的核心闭环，当前适合用于比赛展示、个人使用和小范围共享访问。

## 仓库结构

```text
photo-search/
├── docs/
│   ├── competition-submission.md
│   ├── next-steps.md
│   └── tailscale-remote-access.md
├── photo-search-frontend/
└── photo-search-backend/
```

## 当前能力

### Frontend

路径：`photo-search-frontend/`

- Next.js 单页工作台
- 图片上传与批量上传
- 文本搜图
- 以图搜图
- OCR 搜索入口、上传后自动 OCR、图片详情本地文字识别，以及 OCR 结果回写后端参与检索
- 编码状态轮询
- 原图和缩略图查看
- 移动端友好与基础 PWA 支持

### Backend

路径：`photo-search-backend/`

- FastAPI API
- PostgreSQL + pgvector
- Chinese CLIP 向量生成
- 缩略图生成
- 基于 checksum 的重复上传去重
- 搜索日志统计
- 上传文件静态访问

## 运行闭环

### 1. 首次启动

首次启动需要先构建后端镜像，再启动前后端。

后端：

```bash
cd photo-search-backend
cp .env.example .env
PIP_DEFAULT_TIMEOUT=1200 PIP_RETRIES=20 docker compose build backend
docker compose up -d
```

健康检查：

```bash
curl -s http://localhost:8000/health
```

前端：

```bash
cd ../photo-search-frontend
cp .env.local.example .env.local
# 首次安装依赖时执行
npm install
npm run dev -- --hostname 0.0.0.0
```

打开：

```text
http://localhost:3000
```

### 2. 日常启动

如果你没有修改下面这些内容：

- `photo-search-backend/Dockerfile`
- `photo-search-backend/requirements.txt`
- `photo-search-backend/docker-compose.yml`
- 后端基础镜像相关配置

那么下次启动通常**不需要再次构建**，直接启动即可。

后端：

```bash
cd photo-search-backend
docker compose up -d
```

前端：

```bash
cd ../photo-search-frontend
npm run dev -- --hostname 0.0.0.0
```

### 3. 关闭项目

前端如果是通过终端直接运行的开发服务器，在前端那个终端按：

```text
Ctrl+C
```

后端如果想停止容器但保留数据和镜像：

```bash
cd photo-search-backend
docker compose stop
```

后端如果想停止并移除容器与网络，但保留镜像和数据卷：

```bash
cd photo-search-backend
docker compose down
```

这两种方式下，**下次都不需要重新构建**，除非你改了依赖或镜像配置。

### 4. 何时需要重新构建

只有在这些情况之一发生时，才建议重新构建后端镜像：

- 修改了 `photo-search-backend/Dockerfile`
- 修改了 `photo-search-backend/requirements.txt`
- 增删了系统依赖或 Python 依赖
- 修改了 OCR、Torch、Transformers 这类基础运行环境
- 你想强制让容器重新使用最新镜像层

重新构建命令：

```bash
cd photo-search-backend
PIP_DEFAULT_TIMEOUT=1200 PIP_RETRIES=20 docker compose build backend
docker compose up -d
```

如果构建阶段下载 `torch` 超时，可以继续保留上面的长超时配置；如果仍然不稳定，再考虑切换 `PIP_INDEX_URL`。

### 5. 可选 GPU 模式

如果当前机器的 Docker 可以访问 NVIDIA GPU，可使用：

```bash
cd photo-search-backend
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-build
```

## 端口

- `3000`: 前端
- `8000`: 后端 API
- `5433`: PostgreSQL
- `9000`: MinIO API
- `9001`: MinIO Console

## 当前边界

当前项目已经适合做比赛 Demo，支持“单机部署 + 多设备访问 + 正式账号雏形”。

已支持：

- 个人本地使用
- 局域网访问
- 多账号注册 / 登录
- 多设备按账号隔离上传与检索
- Tailscale 远程共享访问

未支持：

- 完整生产级账号体系
- 强安全权限隔离

## 当前推荐使用顺序

1. 先按上面的“运行闭环”完成首次构建或日常启动
2. 确认 `http://localhost:8000/health` 正常
3. 打开 `http://localhost:3000`
4. 注册或登录账号
5. 上传图片并开始检索
6. 使用结束后，按“关闭项目”一节停止前后端

## 提交与规划文档

- [比赛提交说明](./docs/competition-submission.md)
- [后续规划](./docs/next-steps.md)
- [Tailscale 远程访问](./docs/tailscale-remote-access.md)

## 仓库注意事项

- 不要提交本地环境变量文件
- 不要提交模型权重
- 不要提交运行期缓存或上传数据
- 前端和后端的细节说明分别保留在各自目录 README 中
