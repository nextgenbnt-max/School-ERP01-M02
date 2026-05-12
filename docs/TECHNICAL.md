# Greenwood — School Management System
## Technical Document

> Companion reads: [`DESIGN.md`](./DESIGN.md) · [`BUILD.md`](./BUILD.md)

---

## 1. System Overview

A three-tier full-stack web application:

```
┌────────────────────┐     HTTPS      ┌────────────────────┐
│  Browser (SPA)     │ ─────────────► │  FastAPI backend   │
│  React 19 + Vite/  │   /api/*       │  Uvicorn :8001     │
│  CRA + Tailwind +  │ ◄───────────── │  Python 3.11+      │
│  shadcn/ui         │   JSON / PDF   │                    │
└────────────────────┘                └─────────┬──────────┘
                                                │
                                                ▼
                                       ┌────────────────────┐
                                       │     MongoDB        │
                                       │  AsyncIO driver    │
                                       │  (Motor)           │
                                       └────────────────────┘
```

Outbound integrations: **Stripe Checkout**, **Twilio SMS/WhatsApp**, **Resend email**.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| **Backend framework** | FastAPI 0.110+ | Async, type-safe, auto-docs |
| **DB driver** | Motor (async MongoDB) | Native async, no thread pool |
| **Validation** | Pydantic v2 | Built into FastAPI; strict typing |
| **Auth** | PyJWT (HS256) + bcrypt | Stateless tokens, industry standard |
| **PDF** | reportlab 4 | Pure-Python, no system deps |
| **Frontend** | React 19 + React Router 7 | Modern, ergonomic |
| **Styling** | Tailwind CSS 3 + shadcn/ui | Utility-first; consistent component primitives |
| **HTTP client** | axios | `withCredentials: true` for cookie auth |
| **Toasts** | sonner | Lightweight, accessible |
| **Stripe SDK** | emergentintegrations.payments.stripe.checkout | Project-standard wrapper |
| **Email SDK** | resend 2.x | Official |
| **Process supervisor** | supervisord | Restart on crash + log aggregation |

---

## 3. Repository Layout

```
/app
├── backend/
│   ├── server.py          # All FastAPI routes + models + seed (2700 lines)
│   ├── requirements.txt   # pip freeze of installed deps
│   └── .env               # MONGO_URL, JWT_SECRET, ADMIN_*, TWILIO_*, STRIPE_*, RESEND_*
├── frontend/
│   ├── public/index.html  # Google Fonts link
│   ├── src/
│   │   ├── App.js               # Routes + RoleRouter (admin vs parent layout)
│   │   ├── index.css            # Tailwind layers + CSS vars (palette)
│   │   ├── lib/api.js           # axios instance, formatApiError()
│   │   ├── contexts/
│   │   │   └── AuthContext.jsx  # /auth/me on mount; login/logout
│   │   ├── components/
│   │   │   ├── Layout.jsx
│   │   │   ├── Sidebar.jsx      # 17-item nav (admin)
│   │   │   ├── ProtectedRoute.jsx
│   │   │   ├── PageHeader.jsx
│   │   │   └── ui/              # shadcn primitives
│   │   └── pages/
│   │       ├── Login.jsx
│   │       ├── Dashboard.jsx
│   │       ├── Settings.jsx
│   │       ├── Classes.jsx
│   │       ├── Subjects.jsx
│   │       ├── Students.jsx
│   │       ├── Employees.jsx
│   │       ├── Fees.jsx
│   │       ├── Salary.jsx
│   │       ├── Accounts.jsx
│   │       ├── Attendance.jsx
│   │       ├── Timetable.jsx
│   │       ├── Homework.jsx
│   │       ├── Exams.jsx
│   │       ├── QuestionPapers.jsx
│   │       ├── Behaviour.jsx
│   │       ├── Users.jsx
│   │       ├── Reports.jsx
│   │       ├── Messaging.jsx
│   │       └── ParentDashboard.jsx
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   └── .env               # REACT_APP_BACKEND_URL
├── docs/                  # this folder
│   ├── DESIGN.md
│   ├── TECHNICAL.md
│   └── BUILD.md
└── memory/
    ├── PRD.md
    └── test_credentials.md
```

---

## 4. Environment Variables

### Backend — `/app/backend/.env`

| Variable | Purpose | Required | Example |
|---|---|---|---|
| `MONGO_URL` | Mongo connection string | ✅ | `mongodb://localhost:27017` |
| `DB_NAME` | Database name | ✅ | `school_management` |
| `JWT_SECRET` | Token signing secret (hex, ≥ 32 bytes) | ✅ | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAIL` | Seeded admin login | ✅ | `admin@school.com` |
| `ADMIN_PASSWORD` | Seeded admin password (rotates if changed) | ✅ | `admin123` |
| `CORS_ORIGINS` | Comma-separated allow-list, or `*` | ✅ | `https://app.example.com` |
| `STRIPE_API_KEY` | Stripe secret key | for payments | `sk_test_…` or `sk_live_…` |
| `RESEND_API_KEY` | Resend API key | optional | `re_…` |
| `SENDER_EMAIL` | "from" address for outgoing emails | optional | `noreply@yourdomain.com` |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | optional | `AC…` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | optional | |
| `TWILIO_PHONE_NUMBER` | Verified SMS-capable number | for SMS | `+15555550100` |
| `TWILIO_WHATSAPP_FROM` | Approved WhatsApp sender | for WhatsApp | `whatsapp:+14155238886` |

> Missing integration credentials cause the corresponding endpoints to return `{ status: "skipped" }` instead of failing — the UI keeps working end-to-end.

### Frontend — `/app/frontend/.env`

| Variable | Purpose | Required |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Public origin of the backend (no trailing slash) | ✅ |

The frontend constructs `${REACT_APP_BACKEND_URL}/api/...` for every call.

---

## 5. Process Topology (production)

```
supervisord
├── backend  : uvicorn server:app --host 0.0.0.0 --port 8001
└── frontend : node ./node_modules/.bin/serve -s build -l 3000   (built React)
```

Behind a reverse proxy / Kubernetes ingress that routes:
- `/api/*` → backend `:8001`
- `/*` → frontend `:3000`

The frontend is a single-page app; the reverse proxy must serve `index.html` for any unknown path (history-API routing).

---

## 6. Auth Flow

```
1.  POST /api/auth/login        → set httpOnly access_token + refresh_token cookies
2.  GET  /api/auth/me           → returns user object (cookie-authenticated)
3.  Subsequent API calls        → axios `withCredentials: true` sends cookies
4.  POST /api/auth/logout       → clears cookies
```

Roles:
- `admin` / `teacher` → sent to admin layout
- `parent`            → sent to parent layout (no admin sidebar)
- `student`           → reserved (no UI in current build)

Token lifetimes: access 12h, refresh 7d. Refresh-token rotation is not yet implemented — clients re-login on access expiry.

---

## 7. Data Conventions

- IDs are string UUIDs (`uuid4`). MongoDB `_id` is always projected out (`{"_id": 0}`).
- Datetimes stored as ISO 8601 strings (`datetime.now(timezone.utc).isoformat()`).
- Dates stored as `YYYY-MM-DD` strings.
- Money stored as plain floats in dollars — fine for the volume this app handles; for a cents-precision rewrite use integer cents.
- All MongoDB writes use `.copy()` of the model dict to avoid Motor's `_id` mutation leaking back into the response.

---

## 8. Indexes (created on startup)

```python
await db.users.create_index("email", unique=True)
await db.students.create_index("registration_number", unique=True)
await db.classes.create_index("name")
```

For production with high read volume, also add:
- `fee_invoices` → `(student_id, year, month)`
- `attendance` → `(type, date)` and `(class_id, date)`
- `login_attempts` → `(key, ts)` (and a TTL index dropping records older than 24h)

---

## 9. Logging

Standard Python logging (`logger = logging.getLogger("school-mgmt")`). All errors from third-party integrations (Twilio, Stripe, Resend) are caught, logged at WARN, and surfaced to the caller as `status: failed | skipped` with an `error` field — they never 500.

For production, run with a proper log forwarder (Loki, CloudWatch, Datadog) tailing `/var/log/supervisor/backend.*.log`.

---

## 10. Backups

Mongo is the only stateful component. Backup strategy:

| Frequency | Tool | Retention |
|---|---|---|
| Hourly | `mongodump --uri "$MONGO_URL" -o /backups/hourly/$(date +%Y%m%d_%H)` | 48h |
| Daily | snapshot of above to S3/GCS | 30d |
| Weekly | full archive | 1y |

Restore: `mongorestore --uri "$MONGO_URL" --drop /backups/...`.

---

## 11. Performance Notes

- Seed data adds ~50 documents; typical school deployment will sit at thousands. None of the current queries do `O(n)` scans without an index. Reports use `.find().to_list()` which is bounded by the limit argument (max 20 000 documents).
- PDFs are generated on demand (no cache) — a heavy load of `/slip.pdf` calls could cause CPU spikes. For high-volume schools, cache generated PDFs in object storage keyed on the underlying document hash.
- The dashboard `/api/dashboard/stats` aggregates over all invoices and today's attendance — fine for <50 000 invoices.

---

## 12. Testing

| Layer | Tool | Location |
|---|---|---|
| Backend unit + integration | pytest + httpx | `/app/backend/tests/` |
| Frontend e2e | Playwright via the project's testing agent | reports under `/app/test_reports/iteration_*.json` |

Run the backend tests locally:
```bash
cd /app/backend && pytest tests/ -v
```

The testing agent has produced **93/94 passing tests** across 4 iterations. Reports live at `/app/test_reports/iteration_{1..4}.json`.

---

## 13. Security Posture

| Threat | Mitigation |
|---|---|
| Credential stuffing | Email-scoped 5-in-15-min lockout |
| Stolen access token | Short 12h life; httpOnly cookie; `Secure` flag added in production by reverse proxy |
| Self-promoted admin | `/auth/register` accepts only `role=parent`; admins are created from the admin Users page |
| Deactivated employee | `users.active=false` blocks login at 403 |
| SQL/NoSQL injection | Motor uses parameterised filters; no string concat |
| CSRF | Same-site `Lax` cookies + bearer token fallback. For high-security deployments add a CSRF token on state-changing routes. |
| PII at rest | Encrypted-at-rest depends on the Mongo host (Atlas: enabled by default). |
| Webhook spoofing | Stripe signature verified via `emergentintegrations` |

---

## 14. Operational Endpoints

| URL | Purpose | Auth |
|---|---|---|
| `GET /api/` | Health check | none |
| `GET /api/auth/me` | Current user from cookie | required |
| `POST /api/webhook/stripe` | Stripe webhook receiver | signature-verified |

Add a Kubernetes liveness/readiness probe pointing at `GET /api/` for production deployments.

---

## 15. Compatibility Matrix

| Component | Tested | Min |
|---|---|---|
| Python | 3.11 | 3.10 |
| Node.js | 20 | 18 |
| MongoDB | 7.0 | 4.4 (no `$function` etc. used) |
| Browsers | Chromium 120+, Firefox 120+, Safari 17 | any with ES2020 |

---

## 16. Upgrade Path

1. Backup Mongo.
2. Pull new code.
3. `pip install -r backend/requirements.txt` (or rebuild image).
4. `yarn` in `frontend/` and `yarn build`.
5. Restart processes: `sudo supervisorctl restart backend frontend`.
6. The `seed_initial_data()` startup hook is idempotent — it adds missing collections / docs but never overwrites existing data.

---

## 17. Future Hardening Backlog

- Refresh-token rotation + reuse detection
- Per-route audit log written to a `audit_log` collection
- Field-level encryption for parent contact numbers
- Stripe webhook idempotency keys persisted to a `webhook_events` collection
- Postgres adapter if a customer mandates a SQL store
