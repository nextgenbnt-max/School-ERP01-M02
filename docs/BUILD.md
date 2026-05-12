# Greenwood — School Management System
## Build & Deployment Document

> Companion reads: [`DESIGN.md`](./DESIGN.md) · [`TECHNICAL.md`](./TECHNICAL.md)

This guide walks through bringing Greenwood up in four environments — **local dev**, **single-host Docker Compose**, **Kubernetes**, and managed cloud (**AWS / GCP / Azure**).

---

## 0. Prerequisites (any environment)

- **MongoDB 4.4+** instance (self-hosted or Atlas)
- **Python 3.11**
- **Node.js 20** + **Yarn** (`npm install -g yarn`)
- A public HTTPS hostname for the backend (required for Stripe webhooks and Twilio callbacks; not strictly needed for purely local dev)
- API keys (optional but recommended): Stripe, Twilio (SMS + WhatsApp), Resend

> Seeded credentials after first boot: `admin@school.com / admin123`, `teacher@school.com / teacher123`, `parent@school.com / parent123`.

---

## 1. Local Development (laptop / on-prem dev box)

### 1.1 Install MongoDB
```bash
# macOS
brew tap mongodb/brew && brew install mongodb-community && brew services start mongodb-community

# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y mongodb
sudo systemctl enable --now mongod
```

### 1.2 Backend
```bash
cd /app/backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set env
cat > .env <<EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="school_management"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
ADMIN_EMAIL="admin@school.com"
ADMIN_PASSWORD="admin123"
STRIPE_API_KEY=""
RESEND_API_KEY=""
SENDER_EMAIL="onboarding@resend.dev"
TWILIO_ACCOUNT_SID=""
TWILIO_AUTH_TOKEN=""
TWILIO_PHONE_NUMBER=""
TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"
EOF

uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Verify: `curl http://localhost:8001/api/` → `{ "app": "School Management System", "status": "ok" }`.

### 1.3 Frontend
```bash
cd /app/frontend
yarn install

cat > .env <<EOF
REACT_APP_BACKEND_URL=http://localhost:8001
EOF

yarn start   # opens http://localhost:3000
```

Log in with `admin@school.com / admin123`.

---

## 2. Single-host Docker Compose

A `docker-compose.yml` you can drop next to the repo:

```yaml
version: "3.9"

services:
  mongo:
    image: mongo:7
    volumes: [ "mongo_data:/data/db" ]
    restart: unless-stopped

  backend:
    build: ./backend
    depends_on: [ mongo ]
    environment:
      MONGO_URL: "mongodb://mongo:27017"
      DB_NAME: "school_management"
      JWT_SECRET: "${JWT_SECRET}"
      ADMIN_EMAIL: "${ADMIN_EMAIL:-admin@school.com}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD:-admin123}"
      CORS_ORIGINS: "${CORS_ORIGINS:-*}"
      STRIPE_API_KEY: "${STRIPE_API_KEY:-}"
      RESEND_API_KEY: "${RESEND_API_KEY:-}"
      SENDER_EMAIL: "${SENDER_EMAIL:-onboarding@resend.dev}"
      TWILIO_ACCOUNT_SID: "${TWILIO_ACCOUNT_SID:-}"
      TWILIO_AUTH_TOKEN: "${TWILIO_AUTH_TOKEN:-}"
      TWILIO_PHONE_NUMBER: "${TWILIO_PHONE_NUMBER:-}"
      TWILIO_WHATSAPP_FROM: "${TWILIO_WHATSAPP_FROM:-whatsapp:+14155238886}"
    ports: [ "8001:8001" ]
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      args:
        REACT_APP_BACKEND_URL: "${PUBLIC_BACKEND_URL}"
    ports: [ "3000:3000" ]
    depends_on: [ backend ]
    restart: unless-stopped

volumes:
  mongo_data:
```

### Backend `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Frontend `Dockerfile` (multi-stage)
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY . .
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
RUN yarn build

FROM node:20-alpine
WORKDIR /app
RUN yarn global add serve
COPY --from=build /app/build ./build
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
```

### Bring it up
```bash
export JWT_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')
export PUBLIC_BACKEND_URL="https://school.example.com"   # behind your reverse proxy
docker compose up -d --build
```

Front a Caddy or Nginx reverse proxy in front of both ports to terminate TLS:

```nginx
# /etc/nginx/sites-available/school
server {
    listen 443 ssl http2;
    server_name school.example.com;
    ssl_certificate     /etc/letsencrypt/live/school.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/school.example.com/privkey.pem;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }
}
```

---

## 3. Kubernetes (any cluster — EKS, GKE, AKS, k3s)

Minimal manifests (drop into a `k8s/` folder and `kubectl apply -f k8s/`):

```yaml
# 01-namespace.yaml
apiVersion: v1
kind: Namespace
metadata: { name: school }
---
# 02-mongo.yaml (for non-managed; use Atlas in production)
apiVersion: apps/v1
kind: StatefulSet
metadata: { name: mongo, namespace: school }
spec:
  serviceName: mongo
  replicas: 1
  selector: { matchLabels: { app: mongo } }
  template:
    metadata: { labels: { app: mongo } }
    spec:
      containers:
        - name: mongo
          image: mongo:7
          ports: [{ containerPort: 27017 }]
          volumeMounts: [{ name: data, mountPath: /data/db }]
  volumeClaimTemplates:
    - metadata: { name: data }
      spec:
        accessModes: [ ReadWriteOnce ]
        resources: { requests: { storage: 20Gi } }
---
apiVersion: v1
kind: Service
metadata: { name: mongo, namespace: school }
spec:
  selector: { app: mongo }
  ports: [{ port: 27017, targetPort: 27017 }]
  clusterIP: None
---
# 03-secrets.yaml
apiVersion: v1
kind: Secret
metadata: { name: backend-env, namespace: school }
stringData:
  MONGO_URL: "mongodb://mongo:27017"
  DB_NAME: "school_management"
  JWT_SECRET: "REPLACE_ME_HEX_64"
  ADMIN_EMAIL: "admin@school.com"
  ADMIN_PASSWORD: "REPLACE_ME"
  CORS_ORIGINS: "https://school.example.com"
  STRIPE_API_KEY: ""
  RESEND_API_KEY: ""
  SENDER_EMAIL: "onboarding@resend.dev"
  TWILIO_ACCOUNT_SID: ""
  TWILIO_AUTH_TOKEN: ""
  TWILIO_PHONE_NUMBER: ""
  TWILIO_WHATSAPP_FROM: "whatsapp:+14155238886"
---
# 04-backend.yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: backend, namespace: school }
spec:
  replicas: 2
  selector: { matchLabels: { app: backend } }
  template:
    metadata: { labels: { app: backend } }
    spec:
      containers:
        - name: backend
          image: ghcr.io/yourorg/school-backend:latest
          ports: [{ containerPort: 8001 }]
          envFrom: [{ secretRef: { name: backend-env } }]
          livenessProbe:
            httpGet: { path: /api/, port: 8001 }
            initialDelaySeconds: 10
          readinessProbe:
            httpGet: { path: /api/, port: 8001 }
            initialDelaySeconds: 5
---
apiVersion: v1
kind: Service
metadata: { name: backend, namespace: school }
spec:
  selector: { app: backend }
  ports: [{ port: 8001, targetPort: 8001 }]
---
# 05-frontend.yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: frontend, namespace: school }
spec:
  replicas: 2
  selector: { matchLabels: { app: frontend } }
  template:
    metadata: { labels: { app: frontend } }
    spec:
      containers:
        - name: frontend
          image: ghcr.io/yourorg/school-frontend:latest
          ports: [{ containerPort: 3000 }]
---
apiVersion: v1
kind: Service
metadata: { name: frontend, namespace: school }
spec:
  selector: { app: frontend }
  ports: [{ port: 3000, targetPort: 3000 }]
---
# 06-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: school
  namespace: school
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts: [ school.example.com ]
      secretName: school-tls
  rules:
    - host: school.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend: { service: { name: backend,  port: { number: 8001 } } }
          - path: /
            pathType: Prefix
            backend: { service: { name: frontend, port: { number: 3000 } } }
```

Build & push images:
```bash
docker build -t ghcr.io/yourorg/school-backend:$(git rev-parse --short HEAD) backend/
docker build --build-arg REACT_APP_BACKEND_URL=https://school.example.com \
             -t ghcr.io/yourorg/school-frontend:$(git rev-parse --short HEAD) frontend/
docker push ghcr.io/yourorg/school-backend:...
docker push ghcr.io/yourorg/school-frontend:...
```

---

## 4. Cloud — AWS

| Component | Recommended service |
|---|---|
| Database | **MongoDB Atlas** (multi-region) or **DocumentDB** (Mongo-compatible) |
| Backend | **ECS Fargate** or **EKS** with the Dockerfile above |
| Frontend | **CloudFront + S3** (host the `frontend/build` output) OR Fargate behind the same ALB |
| DNS / TLS | **Route 53 + ACM** |
| Secrets | **AWS Secrets Manager** — mount as env vars |
| Logs | **CloudWatch** via Firelens / Fluent Bit |
| Backups | Atlas automated daily snapshots; or AWS Backup for DocumentDB |

Minimal Fargate task definition (env from Secrets Manager) gets you running in under 30 minutes. Point Stripe webhooks at `https://<alb-domain>/api/webhook/stripe`.

---

## 5. Cloud — GCP

| Component | Recommended service |
|---|---|
| Database | **MongoDB Atlas** on GCP or **Firestore** (would require a small adapter — not provided) |
| Backend | **Cloud Run** (port 8001, autoscale to 0) |
| Frontend | **Firebase Hosting** or **Cloud Run** of the SPA serve image |
| DNS / TLS | Cloud Run managed certs |
| Secrets | **Secret Manager** |
| Logs | **Cloud Logging** (auto) |

Deploy backend with one command:
```bash
gcloud run deploy school-backend \
  --image ghcr.io/yourorg/school-backend:latest \
  --region us-central1 \
  --set-env-vars="DB_NAME=school_management" \
  --set-secrets="MONGO_URL=mongo-url:latest,JWT_SECRET=jwt-secret:latest" \
  --port 8001 --allow-unauthenticated
```

---

## 6. Cloud — Azure

| Component | Recommended service |
|---|---|
| Database | **Cosmos DB for MongoDB** (drop-in) or **Atlas on Azure** |
| Backend | **Azure Container Apps** |
| Frontend | **Static Web Apps** (point to `frontend/build`) |
| DNS / TLS | Container Apps custom domains |
| Secrets | **Key Vault** + Container Apps secret references |
| Logs | **Log Analytics** |

---

## 7. CI/CD Sketch (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: deploy
on: { push: { branches: [ main ] } }

jobs:
  build-test:
    runs-on: ubuntu-latest
    services:
      mongo: { image: mongo:7, ports: ["27017:27017"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && pytest -v
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable && cd frontend && yarn install --frozen-lockfile && yarn lint && yarn build

  publish:
    needs: build-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: ${{ github.actor }}, password: ${{ secrets.GITHUB_TOKEN }} }
      - run: |
          docker build -t ghcr.io/${{ github.repository }}/backend:${{ github.sha }} backend
          docker build --build-arg REACT_APP_BACKEND_URL=${{ vars.PUBLIC_BACKEND_URL }} \
                       -t ghcr.io/${{ github.repository }}/frontend:${{ github.sha }} frontend
          docker push ghcr.io/${{ github.repository }}/backend:${{ github.sha }}
          docker push ghcr.io/${{ github.repository }}/frontend:${{ github.sha }}
```

Add a deploy stage that does `kubectl set image ...` or `aws ecs update-service` / `gcloud run deploy` to roll the new image to your environment.

---

## 8. Post-Deploy Checklist

1. **Confirm `/api/` returns 200** — `curl https://<your-host>/api/`.
2. **Log in as admin** and rotate the seeded password (or set `ADMIN_PASSWORD` to a strong value before first boot — the seed only sets it once).
3. **Set institute branding** at `Settings → Institute profile`.
4. **Add real users** at `Users → New user` (avoid the public `/api/auth/register` for staff — that route is parent-only by design).
5. **Wire Stripe**:
   - Set `STRIPE_API_KEY` (live or test).
   - Configure a webhook in the Stripe dashboard: `POST https://<your-host>/api/webhook/stripe`, event `checkout.session.completed`.
6. **Wire Twilio**: SMS-capable number + WhatsApp sender, then set `TWILIO_*` envs and restart backend.
7. **Wire Resend**: set `RESEND_API_KEY` and `SENDER_EMAIL` to an authenticated domain.
8. **Backup cron**: confirm Mongo backups are running.
9. **Liveness probe** in place (`GET /api/`).
10. **Document the runbook**: who gets paged when the backend pod restarts, where logs live, how to reset a parent password.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/login` shows blank page | Frontend can't reach backend | Confirm `REACT_APP_BACKEND_URL`, check CORS, check browser console |
| Login returns 429 immediately | Email is locked out from earlier brute-force attempts | Wait 15 min, or `db.login_attempts.deleteMany({key:"<email>"})` |
| "Account is deactivated" | `users.active=false` | Set true via Users page or `db.users.updateOne({email:...},{$set:{active:true}})` |
| Stripe redirect → polling never resolves to "paid" | Webhook not reachable | Verify Stripe dashboard event log; ensure `/api/webhook/stripe` is publicly reachable over HTTPS |
| Email sends return `status: skipped` | `RESEND_API_KEY` empty | Set the key and `sudo supervisorctl restart backend` |
| SMS returns `status: skipped` | Twilio creds empty | Set `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_PHONE_NUMBER` |
| Seed re-runs on every restart | This is by design (idempotent); admin password is rotated to match `ADMIN_PASSWORD` env on each boot |
| PDF endpoint returns 404 | Underlying resource (invoice, student, etc.) was deleted | Re-run the workflow from a current record |

---

## 10. Rolling Back

1. Restore the previous Docker image tag (`kubectl set image deploy/backend backend=...:<sha>`).
2. If a migration of seed data is required, restore Mongo from the last backup before the deploy:
   ```bash
   mongorestore --uri "$MONGO_URL" --drop /backups/<timestamp>
   ```
3. Restart frontend pods if config changed.

The schema is implicit (Mongo) — no migrations to undo. New collections introduced by a later version stay in the DB but are simply unused after a rollback.

---

## 11. Capacity Sizing (rule of thumb)

| Students | Backend | Mongo | Frontend |
|---|---|---|---|
| < 500 | 1 × 0.5 vCPU / 512 MB | Atlas M0 (free) | 1 × 256 MB |
| 500 – 2 000 | 2 × 1 vCPU / 1 GB | Atlas M10 | 2 × 256 MB |
| 2 000 – 10 000 | 3 × 2 vCPU / 2 GB | Atlas M20 with replica | 3 × 512 MB behind CDN |

Bottlenecks scale roughly with: number of fee invoices generated per month × number of parents who pay online (Stripe webhook latency).
