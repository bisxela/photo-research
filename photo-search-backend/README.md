# Photo Search Backend

FastAPI backend for image upload, embedding generation, text-to-image search, and image-to-image search.

## Stack

- FastAPI
- PostgreSQL 14 + pgvector
- Chinese CLIP
- MinIO
- Docker Compose

## Current Layout

This backend is intended to live alongside the frontend as a sibling directory:

```text
photo-search-frontend/
photo-search-backend/
```

## What It Does

- Upload single or multiple images
- Generate thumbnails
- Encode images with Chinese CLIP
- Search by text
- Search similar images by image ID
- Expose uploaded originals and thumbnails through `/uploads`

## Prerequisites

- Docker
- Docker Compose
- Model files available under `models/chinese-clip-vit-base-patch16/`

The `models/` directory is ignored for GitHub and should be prepared locally.

## Environment

Create a local env file:

```bash
cp .env.example .env
```

Default configuration is set up for local Docker Compose development.

## Run Locally

From this directory:

```bash
docker compose up -d
```

Check status:

```bash
docker compose ps
```

Health check:

```bash
curl -s http://localhost:8000/health
```

API docs:

```text
http://localhost:8000/docs
```

## Exposed Ports

- `8000`: FastAPI
- `5433`: PostgreSQL on host, mapped to `5432` inside container
- `9000`: MinIO API
- `9001`: MinIO Console

## Notes

- Uploaded files are stored in a Docker volume mounted to `/app/data/uploads`
- Batch upload and embedding generation are available
- GPU is not enabled in the current Docker setup

## Useful Commands

Start:

```bash
docker compose up -d
```

Stop:

```bash
docker compose down
```

Logs:

```bash
docker compose logs -f backend
```
