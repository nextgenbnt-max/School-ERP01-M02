# Greenwood — School Management System
## Design Document

> Companion reads: [`TECHNICAL.md`](./TECHNICAL.md) · [`BUILD.md`](./BUILD.md)

---

## 1. Purpose & Goals

Greenwood is a multi-role school ERP designed for small-to-mid sized institutions (K-12, coaching centres, tuition academies). It replaces a mix of spreadsheets, paper letters and phone calls with one branded portal covering admissions, attendance, fees, payroll, exams, communications and a self-service parent experience.

**Primary goals**
- Deliver a polished, opinionated admin experience that is usable on day one (no setup wizard required — sensible defaults + seeded demo data).
- Treat **role-based access** as a first-class concern (Admin, Teacher, Student, Parent).
- Make every printable artefact (receipts, slips, letters, ID cards, certificates, question papers) a one-click PDF.
- Be easy to self-host (single Docker compose) or run as a managed multi-tenant service.

**Non-goals (out of MVP)**
- Multi-tenant isolation per school inside a single database (the current design is one DB per institute).
- Real-time chat / video classes / LMS courseware.
- Mobile native apps — the web UI is responsive but not packaged as an app.

---

## 2. Personas & Roles

| Role | Primary use | Permissions |
|---|---|---|
| **Admin** | Principal / office manager | Full CRUD on every resource; settings; user management; payroll; accounting |
| **Teacher** | Class teachers, subject teachers | Manage students, attendance, homework, exams, marks; send messages; can also create/edit timetable slots |
| **Student** | Reserved for future portal | Read-only personal view (not implemented in Phase 1–3) |
| **Parent** | Family member | Self-signup; link children by registration number; view per-child attendance, fees, homework; **pay fees online** via Stripe |

Auth enforcement is centralised through two helpers — `get_current_user` (verifies cookie + JWT) and `require_roles(...)` (FastAPI dependency that 403s if the user's role isn't whitelisted).

---

## 3. Information Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Admin Console (Layout)                  │
│  Sidebar (16 modules)                Top-right user chip    │
│  ────────────────────────────────────────────────────────   │
│  Dashboard          Fees                                    │
│  Classes            Salary                                  │
│  Subjects           Accounts                                │
│  Students           Messaging                               │
│  Employees          Reports                                 │
│  Timetable          Users (admin only)                      │
│  Attendance         Settings                                │
│  Homework                                                   │
│  Behaviour & Skills                                         │
│  Exams                                                      │
│  Question Papers                                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                Parent Portal (separate Layout)              │
│  Child switcher  •  3 KPI cards  •  Fees / Homework lists   │
└─────────────────────────────────────────────────────────────┘
```

Routing is role-aware: an authenticated user with `role=parent` is sent to the Parent layout, everyone else to the admin layout (`/app/frontend/src/App.js → RoleRouter`).

---

## 4. Domain Model

All collections use a string UUID `id` field (never the BSON `_id`) to keep JSON serialisation simple. Cross-references store ids; the API joins names on read.

### Core entities

| Collection | Key fields | Notes |
|---|---|---|
| `users` | id, email (unique), password_hash, name, role, active, linked_student_ids, created_at | Parents store one or more linked student ids |
| `institute` | id="default", name, tagline, logo_url, phone, website, address, county, email, rules, grading_scale, discount_types, fee_particulars | Singleton — one row per deployment |
| `classes` | id, name, section, monthly_fee, class_teacher_id, created_at | |
| `subjects` | id, name, code, class_ids[] | M:N to classes via array |
| `students` | id, name, registration_number (unique), class_id, picture_url, admission_date, fee_discount, mobile, dob, gender, cast, identification_marks, previous_school, religion, blood_group, address, additional_note, father_name, father_contact, mother_name, mother_contact, created_at | |
| `employees` | id, name, contact, role, picture_url, joining_date, monthly_salary, spouse_name, pan, gender, experience, email, dob, education, address, created_at | Roles: principal, vice_principal, teacher, accountant, librarian, support_staff |

### Operations

| Collection | Key fields |
|---|---|
| `fee_invoices` | id, student_id, month, year, amount, paid_amount, status (pending\|partial\|paid), due_date, paid_date, payment_method, notes |
| `attendance` | id, type (student\|employee), entity_id, class_id, date (YYYY-MM-DD), status (present\|absent\|late\|leave), notes |
| `salary_slips` | id, employee_id, month, year, base_salary, bonus, deductions, net_amount, status, paid_date, payment_method, notes |
| `accounts` | id, code (unique), name, type (asset\|liability\|income\|expense\|equity), description |
| `transactions` | id, account_id, type (income\|expense), amount, date, description, category, reference |
| `homework` | id, class_id, subject_id, title, description, assigned_date, due_date, attachment_url, created_by |
| `timetable_config` | id="default", weekdays[], periods[{name,start,end}], classrooms[] |
| `timetable_slots` | id, class_id, weekday, period_index, subject_id, teacher_id, classroom |
| `exams` | id, name, class_id, start_date, end_date |
| `exam_subjects` | id, exam_id, subject_id, exam_date, max_marks, pass_marks |
| `exam_results` | id, exam_id, student_id, subject_id, marks, remarks |
| `question_papers` | id, title, subject_id, class_id, duration_minutes, total_marks, instructions, questions[{text, marks}] |
| `behaviour_ratings` / `skill_ratings` | id, student_id, category, rating (1–5), remark, date, rated_by |
| `observations` | id, student_id, note, date, observed_by |
| `messages` | id, channel (sms\|whatsapp), recipient, body, status, twilio_sid, error, sent_at |
| `email_logs` | id, channel, recipient, subject, ref, ref_type, status, error, sent_at |
| `payment_transactions` | id, session_id, invoice_id, student_id, parent_id, amount, currency, payment_status, status, metadata |
| `login_attempts` | id, key (email), success, ts |

### Reference diagram

```
                       institute (singleton)
                              │
        ┌─────────────────────┼─────────────────────┐
     classes              employees               users (roles)
        │                     │                    │
    subjects (M:N)        salary_slips        parent.linked_student_ids ─┐
        │                                                                │
     students ────────┬───────────────┬───────────────┬──────────────────┘
        │             │               │               │
   fee_invoices  attendance       homework      exam_results
        │
   payment_transactions (Stripe)
        │
   transactions ── accounts (chart of accounts)
```

---

## 5. API Surface (selected)

Every route is under `/api`. Auth is via httpOnly cookies set by `/api/auth/login`; bearer-token via `Authorization: Bearer …` is also accepted.

| Area | Endpoints |
|---|---|
| **Auth** | `POST /auth/login`, `POST /auth/register` (parent self-signup only), `POST /auth/logout`, `GET /auth/me` |
| **Institute** | `GET/PUT /institute` |
| **People** | `GET/POST/PUT/DELETE /classes`, `/subjects`, `/students`, `/employees` |
| **Fees** | `GET/POST /fees/invoices`, `POST /fees/invoices/bulk-generate`, `POST /fees/invoices/{id}/pay`, `GET /fees/report`, `GET /fees/invoices/{id}/slip.pdf`, `POST /fees/invoices/{id}/email` |
| **Salary** | `GET/POST /salary/slips`, `POST /salary/slips/bulk-generate`, `POST /salary/slips/{id}/pay`, `GET /salary/report`, `GET /salary/slips/{id}/slip.pdf`, `POST /salary/slips/{id}/email` |
| **Accounts** | `GET/POST/PUT/DELETE /accounts`, `GET/POST/DELETE /transactions`, `GET /accounts/statement` |
| **Attendance** | `POST /attendance/mark`, `GET /attendance`, `GET /attendance/report` |
| **Timetable** | `GET/PUT /timetable/config`, `GET /timetable`, `POST /timetable/slot`, `DELETE /timetable/slot/{id}` |
| **Homework** | `GET/POST/PUT/DELETE /homework` |
| **Exams** | `GET/POST/DELETE /exams`, `GET/POST/DELETE /exams/{id}/subjects`, `GET/POST /exams/{id}/results`, `GET /exams/{id}/marksheet` |
| **Question papers** | `GET/POST/PUT/DELETE /question-papers`, `GET /question-papers/{id}/pdf` |
| **Behaviour** | `GET/POST/DELETE /behaviour-ratings`, `/skill-ratings`, `/observations` |
| **Documents** | `GET /students/{id}/id-card.pdf`, `/admission-letter.pdf`, `/certificate.pdf?type=…`, `/employees/{id}/id-card.pdf`, `/job-letter.pdf` |
| **Comms** | `POST /messages/send`, `GET /messages`, `GET /emails/logs` |
| **Parent** | `GET /parent/children`, `POST /parent/link-child`, `POST /parent/unlink-child`, `GET /parent/children/{student_id}/summary`, `POST /parent/fees/invoices/checkout` |
| **Payments** | `GET /payments/checkout/status/{session_id}`, `POST /webhook/stripe` |
| **Users (admin)** | `GET/POST/PUT/DELETE /users`, `POST /users/{id}/reset-password` |
| **Dashboard** | `GET /dashboard/stats` |

---

## 6. UI Design Principles

- **Light, professional admin aesthetic** — Tailwind tokens centred around an indigo primary (`hsl(239 84% 60%)`) with `IBM Plex Sans` body and `Bricolage Grotesque` display.
- Shadcn components throughout (`/app/frontend/src/components/ui/*`) — no rebuilding of primitives.
- Every interactive element has a `data-testid` for automated testing.
- KPI cards use the `.kpi-card` utility; data tables use `.data-table-th` / `.data-table-td`; cards use `.surface`.
- Parent portal intentionally drops the admin sidebar in favour of a focused single-page view — parents are not power users.

---

## 7. PDF & Document Generation

Generated server-side with `reportlab` for full control over layout and zero JS deps.

A shared helper `_build_pdf_header(institute, title)` prints the institute name (indigo), tagline, address and the document title at the top of every PDF, giving every artefact a consistent brand.

PDFs produced:
- Fee receipt
- Salary slip
- Admission letter
- Student certificates (admission · character · transfer · completion)
- Student ID card
- Staff ID card
- Staff job letter
- Question paper

All endpoints return `Content-Type: application/pdf` and stream the body.

---

## 8. Security Model

| Layer | Mechanism |
|---|---|
| **Transport** | HTTPS via the platform ingress / reverse proxy |
| **Auth** | bcrypt password hashing; JWT (HS256) with 12h access + 7d refresh; httpOnly cookies |
| **Brute force** | Email-scoped sliding-window lockout — 5 fails in 15 min → 429 for 15 min |
| **Authorisation** | `require_roles(...)` dependency at the FastAPI endpoint level |
| **Account lifecycle** | `users.active=false` blocks login (403) without deleting data |
| **Data validation** | Pydantic v2 models on every request; password `min_length=8` |
| **CORS** | configured from `CORS_ORIGINS` env var |
| **Webhook integrity** | Stripe signature verification through `emergentintegrations` |
| **Self-registration** | restricted to `role=parent`; admins cannot be created by the public route |

---

## 9. Integrations

| Integration | Why | Mode |
|---|---|---|
| **Stripe Checkout** | Online fee payment from parent portal | Real, test key pre-provisioned; webhook + cached polling status |
| **Twilio (SMS + WhatsApp)** | Fee reminders, absence alerts, parent comms | Real once `TWILIO_*` envs are set — otherwise returns `status=skipped` |
| **Resend** | Email PDF receipts and salary slips | Real once `RESEND_API_KEY` is set — otherwise returns `status=skipped` |

The "no-key = `skipped`" pattern means the UI works end-to-end before any third-party account exists, making install + first-run trivial.

---

## 10. Extensibility hooks

- **New module** — add a model + routes inside `server.py` (still ~2700 lines; a router split is on the Phase-4 backlog) and a page under `/app/frontend/src/pages/*`. Register the sidebar entry in `Sidebar.jsx`.
- **New PDF document** — write a function returning a `BytesIO`, wrap with `_pdf_response(buf, filename)`.
- **New certificate type** — add a tuple to the `_CERT_TEMPLATES` dict in `server.py`.
- **New rating category** — edit the `BEHAVIOUR_CATS` / `SKILL_CATS` arrays in `/app/frontend/src/pages/Behaviour.jsx`. (Future: persist per institute.)

---

## 11. Known Trade-offs & Backlog

- `server.py` is a single 2700-line file. Functional for the current scope; recommend a router split before adding Phase 4 features.
- Multi-school tenancy is **not** implemented. Each deployment serves one institute.
- Login rate limit is email-scoped (not IP) because the Kubernetes ingress rotates client IPs. This is the correct call for credential-stuffing protection but allows volumetric attacks; couple with platform-level WAF for full coverage.
- The Stripe status endpoint falls back to cached transaction data if `emergentintegrations.get_checkout_status` fails — the Stripe webhook is the source of truth for `paid` status.
- No audit log of admin actions yet (role changes, deletes, password resets).
