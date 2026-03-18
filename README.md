# Photo Search

Monorepo for the image semantic search project.

## Structure

```text
photo-search/
├── photo-search-frontend/
└── photo-search-backend/
```

## Components

### Frontend

Path: `photo-search-frontend/`

- Next.js application
- Upload images
- Text-to-image search
- Image-to-image search
- Poll image encoding status

### Backend

Path: `photo-search-backend/`

- FastAPI service
- PostgreSQL + pgvector
- Chinese CLIP embedding generation
- Thumbnail generation
- Static file exposure for uploaded assets

## Local Development

### 1. Start backend

```bash
cd photo-search-backend
cp .env.example .env
docker compose up -d
```

Health check:

```bash
curl -s http://localhost:8000/health
```

### 2. Start frontend

```bash
cd photo-search-frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## Ports

- `3000`: frontend dev server
- `8000`: backend API
- `5433`: PostgreSQL on host
- `9000`: MinIO API
- `9001`: MinIO console

## GitHub Notes

- Do not commit local env files
- Do not commit model weights
- Do not commit runtime caches or uploaded data
- Frontend and backend each keep their own local README for module-specific details
