# Next Steps

This document records the practical next steps for the current demo phase.

Current goal:

- keep the project usable for yourself and a small group of friends
- avoid unnecessary production complexity
- improve search quality and mobile web experience

## MinIO Decision

## Recommendation

Do **not** switch the current demo to MinIO yet.

## Why

For the current project stage, MinIO does not provide a meaningful performance win.

### What MinIO would improve

- cleaner object-storage style file management
- easier future migration to cloud storage
- better long-term fit for multi-user or production deployment

### What MinIO would not materially improve right now

- CLIP encoding speed
- text/image retrieval quality
- frontend response speed
- small-scale demo usability

### Cost at the current stage

- more deployment complexity
- more moving parts to maintain
- another service to debug
- upload logic needs to be rewritten from local filesystem to object storage

## Conclusion

For the current demo:

- keep image storage on the local Docker volume
- keep MinIO optional / dormant
- spend effort on retrieval quality and user-facing experience first

## Current State Summary

- backend supports image upload, batch upload, thumbnail generation, text search, and similar-image search
- GPU backend mode is available
- backend startup is stabilized with a pre-start wait for PostgreSQL
- image uploads are deduplicated by file checksum
- mobile web access works on iPhone Safari
- minimal PWA support is enabled
- current image gallery has been cleared

## Priority Roadmap

## P1. Improve retrieval quality

Reason:

- current search quality is acceptable for a demo but still noisy
- similarity scores being below `0.5` is not itself the main problem
- ranking quality matters more than the raw number

### Tasks

- rebuild a clean demo gallery with better curated photos
- test search quality on a smaller, more intentional dataset
- compare text search and image search results separately
- collect a short list of “bad queries” and “good queries”
- evaluate whether top-k should be widened and then reranked

### Later improvements

- add tags or lightweight metadata
- add reranking rules
- only evaluate model changes after the above

## P2. Improve mobile web UX

Reason:

- the main usage path is now iPhone Safari + PWA

### Tasks

- continue tuning upload flow for mobile
- make batch upload progress clearer
- improve result card density and readability on small screens
- consider a more explicit “gallery mode” / “detail mode” toggle
- test repeated use from Safari home-screen launch

## P3. Reduce demo complexity

Reason:

- current demo should stay lightweight

### Tasks

- keep MinIO unused for now
- decide later whether MinIO should be removed from the demo compose stack entirely
- keep GPU mode available only when needed

## P4. Small-group sharing

Reason:

- project should be usable by you and a few friends without full productization

### Tasks

- continue using Tailscale for remote access
- document the shortest “start backend / start frontend / open URL” flow
- decide whether all users share one gallery or whether lightweight user separation is needed

## Optional Next Major Feature

If the project grows beyond a personal/shared demo, the next real architecture step is:

- user accounts
- image ownership
- per-user gallery isolation

Do not start this yet unless shared use becomes a real need.

## Suggested Immediate Next Session

When you continue next time, start with these steps:

1. read this file
2. start backend in GPU or CPU mode as needed
3. start frontend with LAN/Tailscale access
4. upload a small, curated image set
5. test and record search quality issues
6. choose one of:
   - retrieval quality tuning
   - mobile UX improvement

## Useful Commands

### Start backend with GPU

```bash
cd /home/abin/projects/photo-search/photo-search-backend
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-build
```

### Start frontend for local/LAN/Tailscale access

```bash
cd /home/abin/projects/photo-search/photo-search-frontend
npm run dev -- --hostname 0.0.0.0
```

### Stop backend

```bash
cd /home/abin/projects/photo-search/photo-search-backend
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
```

### Health check

```bash
curl -s http://localhost:8000/health
```
