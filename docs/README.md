# Greenwood — School Management System Documentation

Three documents:

| File | What's inside |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | Goals, personas, modules, domain model, API surface, UI/UX principles, security model, integrations, extensibility, backlog |
| [`TECHNICAL.md`](./TECHNICAL.md) | Tech stack, repository layout, env vars, process topology, auth flow, indexing, backups, testing, security posture, compatibility matrix |
| [`BUILD.md`](./BUILD.md) | Install on local dev, Docker Compose, Kubernetes, and on AWS / GCP / Azure; CI/CD sketch; post-deploy checklist; troubleshooting; rollback; sizing |

Start with `DESIGN.md` to understand what the app does, then `TECHNICAL.md` to learn how it's built, and finally `BUILD.md` when you're ready to deploy.

## Quick start

```bash
# 1. Local
cd /app/backend && uvicorn server:app --port 8001 --reload
cd /app/frontend && yarn install && yarn start

# 2. Log in
open http://localhost:3000
# admin@school.com / admin123
```

## Test credentials

See [`/app/memory/test_credentials.md`](../memory/test_credentials.md).
