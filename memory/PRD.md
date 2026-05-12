# School Management System — PRD

## Original Problem Statement
Build a webapp for school covering: Dashboard, General Settings (Institute Profile, Fees Particulars/Structure, Discount, Accounts for Fees Invoice, Rules, Marks Grading, Theme/Language, Account settings), Classes, Subjects (assign), Students (full profile incl. parents, admission letter, ID cards, manage login, promote), Employees, Accounts (chart of account, income/expense, statement), Fees (invoice, collect, slip, report), Salary (slip, sheet, report), Attendance (student/employee + reports), Timetable (weekdays, periods, classrooms, generate), Homework, Behaviour & Skills, WhatsApp Integration, Messaging, SMS Services, Question Paper, Exams, Class Tests, Reports, Certificates.

## User Choices
- Modules priority: I decide
- Auth: JWT custom auth (Admin/Teacher/Student/Parent roles)
- 3rd-party: Twilio SMS + Twilio WhatsApp
- Design: Modern professional admin dashboard (light theme, sidebar)
- Seed data: Yes

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB), JWT via PyJWT, bcrypt
- **Frontend**: React 19 + React Router 7 + Tailwind + shadcn/ui
- **DB**: MongoDB (collections: users, institute, classes, subjects, students, employees, fee_invoices, attendance, messages)
- **3rd-party**: Twilio (SMS + WhatsApp) — UI works without credentials, sending requires Twilio SID/Token in .env

## Personas
- **Admin** — full access (CRUD on all entities, settings, fees)
- **Teacher** — students CRUD, attendance, messaging
- **Student / Parent** — (future) read-only personal view

## Implemented (Phase 1) — 2026-02
- Auth: login/register/logout/me (httpOnly cookies, JWT 12h + 7d refresh, bcrypt, role checks)
- Dashboard: 4 KPI cards, fees overview, recent admissions
- General Settings: Institute profile (4 tabs: institute, fees, grading, rules)
- Classes: CRUD + class teacher + monthly fee + student count
- Subjects: CRUD + multi-class assignment
- Students: Full CRUD with all listed fields, search, class filter
- Employees: Full CRUD with role/salary/personal fields
- Fees: monthly invoice generation, collect (partial/full), status filters, by-month report
- Attendance: tabs for student/employee, status (present/absent/late/leave), summary
- Messaging: SMS + WhatsApp via Twilio, recipient picker, templates with tokens, history log
- Reports: Fees report (by month) + Attendance report (per student)
- Seed: admin/teacher users, 5 classes, 6 subjects, 10 employees, 20 students, invoices, today's attendance

## Implemented (Phase 2 — Batch A) — 2026-02
- **Salary**: monthly slips, bulk-generate, mark paid, salary report (payroll/paid/pending + by-month). Marking paid auto-records an EXP-SAL expense transaction. Idempotent (cannot pay twice).
- **Accounts / Chart of Accounts**: 5 account types (asset/liability/income/expense/equity), seeded chart (8 default accounts), income & expense transactions, account statement with running balance.
- **Homework**: CRUD with class + optional subject, due-date highlighting (overdue red, future green), assignable by admin or teacher.
- **Promote Students**: bulk move all students from one class to another.
- **PDF exports**: Fee paid slip, Salary slip, Admission letter — all institute-branded and downloadable.
- Tests: iteration_2 — 22/22 backend + all frontend flows passed.

## Test Credentials (`/app/memory/test_credentials.md`)
- admin@school.com / admin123 — admin
- teacher@school.com / teacher123 — teacher

## Implemented (Phase 2 — Batch B) — 2026-02
- **Timetable**: configurable weekdays/periods/classrooms; per-class grid editor; upsert slots (class+weekday+period unique).
- **Exams**: schedule exams per class with start/end dates; per-exam subjects (max/pass marks); batch marks entry; marksheet endpoint with auto-graded results based on institute grading scale.
- **Question Papers**: full CRUD with question editor (text + per-question marks) and printable PDF export.
- **Letters / ID cards / Certificates**: PDF endpoints for student admission letter, student ID card, student certificates (admission/character/transfer/completion), staff job letter, staff ID card. All branded with institute identity.
- **Parent Portal**: role-aware routing — parents land on a dedicated portal (no admin sidebar). Self-signup restricted to role=parent. Link children by registration number; per-child summary cards: attendance for current month, fee invoices & outstanding for the year, upcoming homework.
- Seed: timetable config + 30 sample slots, 1 Mid-Term Exam with 5 subjects, 1 sample question paper, demo parent `parent@school.com / parent123` linked to 2 students.
- Security/quality fixes: `RegisterIn.password` min_length=8 enforced; teachers can now delete exams (matching their create permission).
- Tests: iteration_3 — 23/23 backend pytest + all new frontend flows passed.

## Implemented (Phase 3 — Polish) — 2026-02
- **Stripe Checkout for parents**: parent clicks Pay on an unpaid invoice → backend creates Stripe Checkout session → redirect → on return, frontend polls /api/payments/checkout/status which now resilient-falls-back to cached transaction record if Stripe lookup fails. Successful payments auto-mark invoice paid AND record an INC-FEE income transaction in the chart of accounts.
- **Resend Email PDF delivery**: Mail icons on Fees and Salary rows email institute-branded PDF receipts. When `RESEND_API_KEY` is blank, endpoints return `{status: 'skipped'}` and log the attempt to `email_logs` collection (`GET /api/emails/logs`).
- **Admin User Management** (`/users`): list, create (any role, password ≥ 8 chars), inline role change, active/inactive toggle (deactivated users blocked at login with 403), reset password, delete (with self-delete protection).
- **Behaviour & Skills** (`/behaviour`): per-student tabs for Behaviours, Skills (1–5 star ratings, configurable categories) and Observations (free-text journal). Category averages displayed.
- **Rate-limited login**: 5 failed attempts on the same email within 15 minutes → 429 lockout for 15 min. Email-scoped (not IP) because the k8s ingress rotates client IPs. Counter resets on successful login.
- **Stripe status resilience fix**: graceful fallback to cached payment_transactions when emergentintegrations `get_checkout_status` fails — webhook remains source of truth for actual paid status.
- Tests: iteration_4 — 25/26 backend pass (the 1 failure was fixed in-iteration).

## Deferred Backlog (Future Phase 4)
- **P3**: Split `server.py` (now 2700+ lines) into per-feature routers
- **P3**: Provide Twilio + Resend production credentials
- **P3**: Stripe receipt email on success; refunds endpoint
- **P3**: Behaviour categories editable per institute
- **P3**: Audit log for admin actions (role changes, deletes, password resets)

## Next Tasks
1. Collect Twilio credentials and configure `.env` (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`)
2. Add Phase 2 modules in priority order
3. Add PDF export for fee slips and admission letters
