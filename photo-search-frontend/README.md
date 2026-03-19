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

If you want to pin the backend host explicitly, set:

```env
NEXT_PUBLIC_API_BASE_URL=http://<your-host-ip>:8000
```

If this env var is not set, the frontend falls back to the current page hostname and assumes the backend is on port `8000`.

## Run Locally

Install dependencies once:

```bash
npm install
```

Start the development server:

```bash
npm run dev -- --hostname 0.0.0.0
```

Open:

```text
http://localhost:3000
```

For another device on the same LAN, open:

```text
http://<your-host-ip>:3000
```

Example:

```text
http://192.168.1.23:3000
```

Make sure:

- the backend is running on `0.0.0.0:8000`
- the frontend dev server is reachable on your LAN
- the phone and your computer are on the same network
- local firewall rules are not blocking ports `3000` and `8000`

## Development Notes

- The page is optimized for local frontend-backend integration
- Remote image optimization is disabled per result image to allow local backend assets
- System fonts are used, so no Google Fonts download is required
- A minimal PWA manifest and app icons are included for mobile Safari add-to-home-screen usage
- The current target is a mobile-friendly web demo, not a native iOS client

## iPhone Safari Usage

Open the frontend on iPhone Safari using your host machine LAN IP, then:

1. Tap the Safari share button
2. Choose `Add to Home Screen`
3. Launch it from the home screen as a standalone web app

This is a lightweight PWA setup:

- standalone launch mode
- app icon
- theme color

It does not yet include offline caching or a service worker.

## Useful Commands

Start dev server:

```bash
npm run dev
```

Lint:

```bash
npm run lint
```
