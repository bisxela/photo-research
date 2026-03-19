# Tailscale Remote Access

This document shows how to access the local Photo Search web app and backend from outside the current LAN using Tailscale.

## Why Tailscale

The current project is a local service:

- frontend on port `3000`
- backend on port `8000`

Without Tailscale, access is limited to:

- the same Wi-Fi / hotspot
- devices that can directly reach your host LAN IP

Tailscale creates a private network between your devices, so your iPhone can reach your Linux machine even when they are not on the same local network.

Official docs:

- Linux install: https://tailscale.com/docs/install/linux
- Install overview: https://tailscale.com/docs/install
- Quickstart: https://tailscale.com/docs/install/start

## What You Need

- a Tailscale account
- Tailscale installed on your Ubuntu host
- Tailscale installed on your iPhone
- the project running locally on the Ubuntu host

## Host Setup (Ubuntu 22.04)

Install Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Bring the machine online:

```bash
sudo tailscale up
```

This prints a login URL. Open it in a browser and authenticate.

After login, check the assigned Tailscale IP:

```bash
tailscale ip -4
```

You can also inspect status:

```bash
tailscale status
```

## Start the Project for Remote Access

### Backend

GPU mode:

```bash
cd /home/abin/projects/photo-search/photo-search-backend
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-build
```

CPU mode:

```bash
cd /home/abin/projects/photo-search/photo-search-backend
docker compose up -d
```

### Frontend

Start the Next.js dev server on all interfaces:

```bash
cd /home/abin/projects/photo-search/photo-search-frontend
npm run dev -- --hostname 0.0.0.0
```

This is required so the frontend is reachable through the Tailscale interface.

## iPhone Setup

1. Install the Tailscale iPhone app from the App Store
2. Log in using the same Tailscale account
3. Confirm both devices appear in the same tailnet

## Access URLs

Get the Ubuntu host Tailscale IPv4:

```bash
tailscale ip -4
```

Assume it returns:

```text
100.101.102.103
```

Then open these from iPhone:

- frontend: `http://100.101.102.103:3000`
- backend health: `http://100.101.102.103:8000/health`

Because the frontend derives the backend host from the current page hostname, opening the frontend over Tailscale will also make frontend API calls target the Tailscale host on port `8000`.

## Optional: Use MagicDNS

If MagicDNS is enabled in Tailscale, you may be able to use the machine name instead of the raw Tailscale IP.

Example:

```text
http://abin-lenovo:3000
```

Use `tailscale status` to inspect names currently visible in your tailnet.

## Verification

On Ubuntu:

```bash
tailscale status
tailscale ip -4
curl -s http://localhost:8000/health
```

On iPhone:

- open the Tailscale IP on port `3000`
- press `检查后端`

## Common Problems

### Tailscale installed but not connected

Run:

```bash
sudo tailscale up
```

### Frontend opens but API fails

Make sure backend is running on the host and reachable:

```bash
curl -s http://localhost:8000/health
```

### Frontend works on host but not remotely

Make sure Next.js is started with:

```bash
npm run dev -- --hostname 0.0.0.0
```

### Want a permanent service later

For long-term usage, move the frontend from `next dev` to a production build and run it behind a reverse proxy.
