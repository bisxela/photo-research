# Photo Search Frontend

Next.js frontend for local interaction with the Photo Search backend.

## Stack

- Next.js
- React
- Tailwind CSS

## Current Layout

This frontend is intended to live alongside the backend as a sibling directory:

```text
photo-search-frontend/
photo-search-backend/
```

## What It Does

- Check backend health
- Upload single or multiple images
- Poll image encoding status after upload
- Search by text
- Search similar images
- View thumbnails and originals

## Environment

Create a local env file if needed:

```bash
cp .env.local.example .env.local
```

Default value:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Run Locally

Install dependencies once:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

## Development Notes

- The page is optimized for local frontend-backend integration
- Remote image optimization is disabled per result image to allow local backend assets
- System fonts are used, so no Google Fonts download is required

## Useful Commands

Start dev server:

```bash
npm run dev
```

Lint:

```bash
npm run lint
```
