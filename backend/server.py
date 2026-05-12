from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import bcrypt
import jwt
import secrets
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ─── Setup ────────────────────────────────────────────────────────────────────
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("school-mgmt")

app = FastAPI(title="School Management System")
api = APIRouter(prefix="/api")


# ─── Helpers ──────────────────────────────────────────────────────────────────
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else dt


def gen_id() -> str:
    return str(uuid.uuid4())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": now_utc() + timedelta(hours=12), "type": "access"},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def create_refresh_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": now_utc() + timedelta(days=7), "type": "refresh"},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def clean(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return doc
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dep


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=False, samesite="lax", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")


# ─── Models ───────────────────────────────────────────────────────────────────
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "parent"


class InstituteIn(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    county: Optional[str] = None
    email: Optional[str] = None
    rules: Optional[str] = None
    grading_scale: Optional[List[Dict[str, Any]]] = None
    discount_types: Optional[List[str]] = None
    fee_particulars: Optional[List[str]] = None


class ClassIn(BaseModel):
    name: str
    monthly_fee: float = 0
    class_teacher_id: Optional[str] = None
    section: Optional[str] = None


class SubjectIn(BaseModel):
    name: str
    code: Optional[str] = None
    class_ids: List[str] = []


class StudentIn(BaseModel):
    name: str
    registration_number: str
    class_id: Optional[str] = None
    picture_url: Optional[str] = None
    admission_date: Optional[str] = None
    fee_discount: float = 0
    mobile: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    cast: Optional[str] = None
    identification_marks: Optional[str] = None
    previous_school: Optional[str] = None
    religion: Optional[str] = None
    blood_group: Optional[str] = None
    address: Optional[str] = None
    additional_note: Optional[str] = None
    father_name: Optional[str] = None
    father_contact: Optional[str] = None
    mother_name: Optional[str] = None
    mother_contact: Optional[str] = None


class EmployeeIn(BaseModel):
    name: str
    contact: Optional[str] = None
    role: str = "teacher"
    picture_url: Optional[str] = None
    joining_date: Optional[str] = None
    monthly_salary: float = 0
    spouse_name: Optional[str] = None
    pan: Optional[str] = None
    gender: Optional[str] = None
    experience: Optional[str] = None
    email: Optional[str] = None
    dob: Optional[str] = None
    education: Optional[str] = None
    address: Optional[str] = None


class FeeInvoiceIn(BaseModel):
    student_id: str
    month: int
    year: int
    amount: float
    due_date: Optional[str] = None
    notes: Optional[str] = None


class FeePaymentIn(BaseModel):
    paid_amount: float
    payment_method: str = "cash"
    notes: Optional[str] = None


class AttendanceMarkIn(BaseModel):
    type: str  # student | employee
    date: str  # YYYY-MM-DD
    class_id: Optional[str] = None
    records: List[Dict[str, str]]  # [{entity_id, status, notes?}]


class MessageIn(BaseModel):
    channel: str  # sms | whatsapp
    recipients: List[str]
    body: str


# ─── Auth ─────────────────────────────────────────────────────────────────────
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60   # 15 min sliding window
LOGIN_LOCKOUT_SECONDS = 15 * 60  # 15 min lockout once tripped


async def _check_login_lockout(key: str):
    now = now_utc()
    window_start = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    # count recent failed attempts
    cnt = await db.login_attempts.count_documents({
        "key": key,
        "success": False,
        "ts": {"$gte": iso(window_start)},
    })
    if cnt >= LOGIN_MAX_ATTEMPTS:
        # find the oldest attempt in the window to compute remaining lockout
        latest = await db.login_attempts.find_one(
            {"key": key, "success": False}, {"_id": 0}, sort=[("ts", -1)],
        )
        remaining = LOGIN_LOCKOUT_SECONDS
        if latest:
            try:
                latest_dt = datetime.fromisoformat(latest["ts"])
                remaining = max(0, LOGIN_LOCKOUT_SECONDS - int((now - latest_dt).total_seconds()))
            except Exception:
                pass
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {remaining // 60 + 1} minutes.")


async def _record_login_attempt(key: str, success: bool):
    await db.login_attempts.insert_one({
        "id": gen_id(), "key": key, "success": success, "ts": iso(now_utc()),
    })
    if success:
        # clear failures on success
        await db.login_attempts.delete_many({"key": key, "success": False})


@api.post("/auth/login")
async def login(data: LoginIn, request: Request, response: Response):
    email = data.email.lower()
    key = email  # email-scoped lockout (ingress may rotate client IPs)
    await _check_login_lockout(key)
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        await _record_login_attempt(key, False)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("active") is False:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    await _record_login_attempt(key, True)
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": clean(user), "access_token": access}


@api.post("/auth/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    # public self-registration is restricted to "parent" role; admins create other roles via dashboard
    if data.role != "parent":
        raise HTTPException(status_code=403, detail="Only 'parent' self-registration is allowed")
    user_doc = {
        "id": gen_id(),
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name,
        "role": data.role,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user_doc)
    access = create_access_token(user_doc["id"], user_doc["email"], user_doc["role"])
    refresh = create_refresh_token(user_doc["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": clean({**user_doc}), "access_token": access}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ─── Institute ────────────────────────────────────────────────────────────────
@api.get("/institute")
async def get_institute():
    doc = await db.institute.find_one({"id": "default"}, {"_id": 0})
    if not doc:
        doc = {"id": "default", "name": "My School", "tagline": "Empowering minds, shaping futures"}
    return doc


@api.put("/institute")
async def update_institute(data: InstituteIn, _: dict = Depends(require_roles("admin"))):
    update = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    update["updated_at"] = iso(now_utc())
    await db.institute.update_one({"id": "default"}, {"$set": update, "$setOnInsert": {"id": "default"}}, upsert=True)
    doc = await db.institute.find_one({"id": "default"}, {"_id": 0})
    return doc


# ─── Classes ──────────────────────────────────────────────────────────────────
@api.get("/classes")
async def list_classes(_: dict = Depends(get_current_user)):
    items = await db.classes.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    # attach teacher names + student count
    for c in items:
        c["student_count"] = await db.students.count_documents({"class_id": c["id"]})
        if c.get("class_teacher_id"):
            t = await db.employees.find_one({"id": c["class_teacher_id"]}, {"_id": 0, "name": 1})
            c["class_teacher_name"] = t["name"] if t else None
    return items


@api.post("/classes")
async def create_class(data: ClassIn, _: dict = Depends(require_roles("admin"))):
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.classes.insert_one(doc.copy())
    return doc


@api.put("/classes/{class_id}")
async def update_class(class_id: str, data: ClassIn, _: dict = Depends(require_roles("admin"))):
    await db.classes.update_one({"id": class_id}, {"$set": data.model_dump()})
    return await db.classes.find_one({"id": class_id}, {"_id": 0})


@api.delete("/classes/{class_id}")
async def delete_class(class_id: str, _: dict = Depends(require_roles("admin"))):
    await db.classes.delete_one({"id": class_id})
    return {"ok": True}


# ─── Subjects ─────────────────────────────────────────────────────────────────
@api.get("/subjects")
async def list_subjects(_: dict = Depends(get_current_user)):
    items = await db.subjects.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    return items


@api.post("/subjects")
async def create_subject(data: SubjectIn, _: dict = Depends(require_roles("admin"))):
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.subjects.insert_one(doc.copy())
    return doc


@api.put("/subjects/{subject_id}")
async def update_subject(subject_id: str, data: SubjectIn, _: dict = Depends(require_roles("admin"))):
    await db.subjects.update_one({"id": subject_id}, {"$set": data.model_dump()})
    return await db.subjects.find_one({"id": subject_id}, {"_id": 0})


@api.delete("/subjects/{subject_id}")
async def delete_subject(subject_id: str, _: dict = Depends(require_roles("admin"))):
    await db.subjects.delete_one({"id": subject_id})
    return {"ok": True}


@api.get("/subjects/by-class/{class_id}")
async def subjects_by_class(class_id: str, _: dict = Depends(get_current_user)):
    items = await db.subjects.find({"class_ids": class_id}, {"_id": 0}).to_list(1000)
    return items


# ─── Students ─────────────────────────────────────────────────────────────────
@api.get("/students")
async def list_students(
    q: Optional[str] = None,
    class_id: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {}
    if class_id:
        flt["class_id"] = class_id
    if q:
        flt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"registration_number": {"$regex": q, "$options": "i"}},
            {"father_name": {"$regex": q, "$options": "i"}},
        ]
    items = await db.students.find(flt, {"_id": 0}).sort("created_at", -1).to_list(2000)
    cls_map = {c["id"]: c.get("name") for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    for s in items:
        s["class_name"] = cls_map.get(s.get("class_id"))
    return items


@api.get("/students/{student_id}")
async def get_student(student_id: str, _: dict = Depends(get_current_user)):
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Student not found")
    if s.get("class_id"):
        c = await db.classes.find_one({"id": s["class_id"]}, {"_id": 0})
        s["class"] = c
    return s


@api.post("/students")
async def create_student(data: StudentIn, _: dict = Depends(require_roles("admin", "teacher"))):
    if await db.students.find_one({"registration_number": data.registration_number}):
        raise HTTPException(400, "Registration number already exists")
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.students.insert_one(doc.copy())
    return doc


@api.put("/students/{student_id}")
async def update_student(student_id: str, data: StudentIn, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.students.update_one({"id": student_id}, {"$set": data.model_dump()})
    return await db.students.find_one({"id": student_id}, {"_id": 0})


@api.delete("/students/{student_id}")
async def delete_student(student_id: str, _: dict = Depends(require_roles("admin"))):
    await db.students.delete_one({"id": student_id})
    return {"ok": True}


# ─── Employees ────────────────────────────────────────────────────────────────
@api.get("/employees")
async def list_employees(q: Optional[str] = None, role: Optional[str] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if role:
        flt["role"] = role
    if q:
        flt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"contact": {"$regex": q, "$options": "i"}},
        ]
    items = await db.employees.find(flt, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.get("/employees/{employee_id}")
async def get_employee(employee_id: str, _: dict = Depends(get_current_user)):
    e = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Employee not found")
    return e


@api.post("/employees")
async def create_employee(data: EmployeeIn, _: dict = Depends(require_roles("admin"))):
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.employees.insert_one(doc.copy())
    return doc


@api.put("/employees/{employee_id}")
async def update_employee(employee_id: str, data: EmployeeIn, _: dict = Depends(require_roles("admin"))):
    await db.employees.update_one({"id": employee_id}, {"$set": data.model_dump()})
    return await db.employees.find_one({"id": employee_id}, {"_id": 0})


@api.delete("/employees/{employee_id}")
async def delete_employee(employee_id: str, _: dict = Depends(require_roles("admin"))):
    await db.employees.delete_one({"id": employee_id})
    return {"ok": True}


# ─── Fees ─────────────────────────────────────────────────────────────────────
@api.get("/fees/invoices")
async def list_invoices(
    student_id: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {}
    if student_id:
        flt["student_id"] = student_id
    if status:
        flt["status"] = status
    if month:
        flt["month"] = month
    if year:
        flt["year"] = year
    invs = await db.fee_invoices.find(flt, {"_id": 0}).sort("created_at", -1).to_list(5000)
    s_ids = list({i["student_id"] for i in invs})
    students = await db.students.find({"id": {"$in": s_ids}}, {"_id": 0, "id": 1, "name": 1, "registration_number": 1, "class_id": 1}).to_list(2000)
    s_map = {s["id"]: s for s in students}
    for inv in invs:
        s = s_map.get(inv["student_id"], {})
        inv["student_name"] = s.get("name")
        inv["registration_number"] = s.get("registration_number")
    return invs


@api.post("/fees/invoices")
async def create_invoice(data: FeeInvoiceIn, _: dict = Depends(require_roles("admin"))):
    doc = {
        "id": gen_id(),
        **data.model_dump(),
        "paid_amount": 0,
        "status": "pending",
        "paid_date": None,
        "payment_method": None,
        "created_at": iso(now_utc()),
    }
    await db.fee_invoices.insert_one(doc.copy())
    return doc


@api.post("/fees/invoices/bulk-generate")
async def bulk_generate(month: int, year: int, class_id: Optional[str] = None, _: dict = Depends(require_roles("admin"))):
    flt: Dict[str, Any] = {}
    if class_id:
        flt["class_id"] = class_id
    students = await db.students.find(flt, {"_id": 0}).to_list(5000)
    cls = await db.classes.find({}, {"_id": 0}).to_list(1000)
    cls_map = {c["id"]: c for c in cls}
    created = 0
    for s in students:
        existing = await db.fee_invoices.find_one({"student_id": s["id"], "month": month, "year": year})
        if existing:
            continue
        c = cls_map.get(s.get("class_id"))
        base = float((c or {}).get("monthly_fee") or 0)
        discount = float(s.get("fee_discount") or 0)
        amount = max(0, base - discount)
        doc = {
            "id": gen_id(), "student_id": s["id"], "month": month, "year": year,
            "amount": amount, "paid_amount": 0, "status": "pending",
            "due_date": f"{year}-{month:02d}-10", "notes": None,
            "paid_date": None, "payment_method": None, "created_at": iso(now_utc()),
        }
        await db.fee_invoices.insert_one(doc.copy())
        created += 1
    return {"created": created}


@api.post("/fees/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: str, data: FeePaymentIn, _: dict = Depends(require_roles("admin"))):
    inv = await db.fee_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    new_paid = (inv.get("paid_amount") or 0) + data.paid_amount
    status = "paid" if new_paid >= inv["amount"] else "partial"
    update = {
        "paid_amount": new_paid,
        "status": status,
        "paid_date": iso(now_utc()),
        "payment_method": data.payment_method,
        "notes": data.notes,
    }
    await db.fee_invoices.update_one({"id": invoice_id}, {"$set": update})
    return await db.fee_invoices.find_one({"id": invoice_id}, {"_id": 0})


@api.get("/fees/report")
async def fees_report(year: Optional[int] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if year:
        flt["year"] = year
    invs = await db.fee_invoices.find(flt, {"_id": 0}).to_list(10000)
    total = sum(float(i["amount"]) for i in invs)
    collected = sum(float(i.get("paid_amount") or 0) for i in invs)
    pending = total - collected
    by_month = {}
    for i in invs:
        key = f"{i['year']}-{i['month']:02d}"
        by_month.setdefault(key, {"month": key, "billed": 0, "collected": 0})
        by_month[key]["billed"] += float(i["amount"])
        by_month[key]["collected"] += float(i.get("paid_amount") or 0)
    return {
        "total_billed": round(total, 2),
        "total_collected": round(collected, 2),
        "total_pending": round(pending, 2),
        "by_month": sorted(by_month.values(), key=lambda x: x["month"]),
    }


# ─── Attendance ───────────────────────────────────────────────────────────────
@api.post("/attendance/mark")
async def mark_attendance(data: AttendanceMarkIn, _: dict = Depends(require_roles("admin", "teacher"))):
    # Remove existing entries for same date/type/class
    flt = {"type": data.type, "date": data.date}
    if data.class_id:
        flt["class_id"] = data.class_id
    await db.attendance.delete_many({**flt, "entity_id": {"$in": [r["entity_id"] for r in data.records]}})
    docs = []
    for r in data.records:
        docs.append({
            "id": gen_id(),
            "type": data.type,
            "entity_id": r["entity_id"],
            "class_id": data.class_id,
            "date": data.date,
            "status": r.get("status", "present"),
            "notes": r.get("notes"),
            "created_at": iso(now_utc()),
        })
    if docs:
        await db.attendance.insert_many([d.copy() for d in docs])
    return {"marked": len(docs)}


@api.get("/attendance")
async def get_attendance(
    type: str,
    date: Optional[str] = None,
    class_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {"type": type}
    if date:
        flt["date"] = date
    if class_id:
        flt["class_id"] = class_id
    if entity_id:
        flt["entity_id"] = entity_id
    if start and end:
        flt["date"] = {"$gte": start, "$lte": end}
    items = await db.attendance.find(flt, {"_id": 0}).to_list(10000)
    return items


@api.get("/attendance/report")
async def attendance_report(
    type: str = "student",
    class_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {"type": type}
    if class_id:
        flt["class_id"] = class_id
    if start and end:
        flt["date"] = {"$gte": start, "$lte": end}
    items = await db.attendance.find(flt, {"_id": 0}).to_list(20000)
    summary: Dict[str, Dict[str, Any]] = {}
    for a in items:
        eid = a["entity_id"]
        summary.setdefault(eid, {"entity_id": eid, "present": 0, "absent": 0, "late": 0, "leave": 0, "total": 0})
        summary[eid][a["status"]] = summary[eid].get(a["status"], 0) + 1
        summary[eid]["total"] += 1
    # attach names
    if type == "student":
        ids = list(summary.keys())
        students = await db.students.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "registration_number": 1}).to_list(2000)
        s_map = {s["id"]: s for s in students}
        for k, v in summary.items():
            s = s_map.get(k, {})
            v["name"] = s.get("name")
            v["registration_number"] = s.get("registration_number")
    else:
        ids = list(summary.keys())
        emps = await db.employees.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(2000)
        e_map = {e["id"]: e for e in emps}
        for k, v in summary.items():
            e = e_map.get(k, {})
            v["name"] = e.get("name")
            v["role"] = e.get("role")
    return list(summary.values())


# ─── Messaging (Twilio SMS + WhatsApp) ────────────────────────────────────────
def _twilio_client():
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not token:
        return None
    try:
        from twilio.rest import Client as TwClient
        return TwClient(sid, token)
    except Exception as e:
        logger.warning(f"Twilio init failed: {e}")
        return None


@api.get("/messages")
async def list_messages(_: dict = Depends(get_current_user)):
    items = await db.messages.find({}, {"_id": 0}).sort("sent_at", -1).limit(200).to_list(200)
    return items


@api.post("/messages/send")
async def send_messages(data: MessageIn, _: dict = Depends(require_roles("admin", "teacher"))):
    if data.channel not in ("sms", "whatsapp"):
        raise HTTPException(400, "Invalid channel")
    tw = _twilio_client()
    from_number = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()
    wa_from = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
    results = []
    for recipient in data.recipients:
        msg_doc = {
            "id": gen_id(), "channel": data.channel, "recipient": recipient,
            "body": data.body, "status": "pending", "twilio_sid": None,
            "error": None, "sent_at": iso(now_utc()),
        }
        if not tw:
            msg_doc["status"] = "skipped"
            msg_doc["error"] = "Twilio credentials not configured"
        else:
            try:
                if data.channel == "sms":
                    if not from_number:
                        raise RuntimeError("TWILIO_PHONE_NUMBER not configured")
                    m = tw.messages.create(body=data.body, from_=from_number, to=recipient)
                else:
                    to_wa = recipient if recipient.startswith("whatsapp:") else f"whatsapp:{recipient}"
                    fr_wa = wa_from if wa_from.startswith("whatsapp:") else f"whatsapp:{wa_from}"
                    m = tw.messages.create(body=data.body, from_=fr_wa, to=to_wa)
                msg_doc["status"] = "sent"
                msg_doc["twilio_sid"] = m.sid
            except Exception as e:
                msg_doc["status"] = "failed"
                msg_doc["error"] = str(e)
        await db.messages.insert_one(msg_doc.copy())
        results.append({k: msg_doc[k] for k in ("id", "recipient", "status", "error")})
    return {"results": results}


# ─── Salary ───────────────────────────────────────────────────────────────────
class SalarySlipIn(BaseModel):
    employee_id: str
    month: int
    year: int
    base_salary: float
    bonus: float = 0
    deductions: float = 0
    notes: Optional[str] = None


class SalaryPayIn(BaseModel):
    payment_method: str = "bank"
    notes: Optional[str] = None


@api.get("/salary/slips")
async def list_salary_slips(
    month: Optional[int] = None, year: Optional[int] = None,
    employee_id: Optional[str] = None, status: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {}
    if month: flt["month"] = month
    if year: flt["year"] = year
    if employee_id: flt["employee_id"] = employee_id
    if status: flt["status"] = status
    slips = await db.salary_slips.find(flt, {"_id": 0}).sort("created_at", -1).to_list(5000)
    ids = list({s["employee_id"] for s in slips})
    emps = await db.employees.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(2000)
    e_map = {e["id"]: e for e in emps}
    for s in slips:
        e = e_map.get(s["employee_id"], {})
        s["employee_name"] = e.get("name")
        s["employee_role"] = e.get("role")
    return slips


@api.post("/salary/slips")
async def create_salary_slip(data: SalarySlipIn, _: dict = Depends(require_roles("admin"))):
    net = max(0, data.base_salary + data.bonus - data.deductions)
    doc = {
        "id": gen_id(), **data.model_dump(),
        "net_amount": net, "status": "pending", "paid_date": None, "payment_method": None,
        "created_at": iso(now_utc()),
    }
    await db.salary_slips.insert_one(doc.copy())
    return doc


@api.post("/salary/slips/bulk-generate")
async def bulk_generate_salary(month: int, year: int, _: dict = Depends(require_roles("admin"))):
    emps = await db.employees.find({}, {"_id": 0}).to_list(1000)
    created = 0
    for e in emps:
        if await db.salary_slips.find_one({"employee_id": e["id"], "month": month, "year": year}):
            continue
        base = float(e.get("monthly_salary") or 0)
        doc = {
            "id": gen_id(), "employee_id": e["id"], "month": month, "year": year,
            "base_salary": base, "bonus": 0, "deductions": 0, "net_amount": base,
            "status": "pending", "paid_date": None, "payment_method": None, "notes": None,
            "created_at": iso(now_utc()),
        }
        await db.salary_slips.insert_one(doc.copy())
        created += 1
    return {"created": created}


@api.post("/salary/slips/{slip_id}/pay")
async def pay_salary_slip(slip_id: str, data: SalaryPayIn, _: dict = Depends(require_roles("admin"))):
    slip = await db.salary_slips.find_one({"id": slip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(404, "Slip not found")
    if slip.get("status") == "paid":
        raise HTTPException(400, "Salary slip is already paid")
    await db.salary_slips.update_one({"id": slip_id}, {"$set": {
        "status": "paid", "paid_date": iso(now_utc()),
        "payment_method": data.payment_method, "notes": data.notes,
    }})
    # auto-record as an expense transaction
    salary_acct = await db.accounts.find_one({"code": "EXP-SAL"})
    if salary_acct:
        await db.transactions.insert_one({
            "id": gen_id(), "account_id": salary_acct["id"], "type": "expense",
            "amount": float(slip["net_amount"]),
            "date": date.today().isoformat(),
            "description": f"Salary {slip['month']}/{slip['year']} — {slip.get('employee_id')}",
            "category": "salary", "reference": slip_id, "created_at": iso(now_utc()),
        })
    return await db.salary_slips.find_one({"id": slip_id}, {"_id": 0})


@api.delete("/salary/slips/{slip_id}")
async def delete_salary_slip(slip_id: str, _: dict = Depends(require_roles("admin"))):
    await db.salary_slips.delete_one({"id": slip_id})
    return {"ok": True}


@api.get("/salary/report")
async def salary_report(year: Optional[int] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if year: flt["year"] = year
    slips = await db.salary_slips.find(flt, {"_id": 0}).to_list(10000)
    total_payroll = sum(float(s["net_amount"]) for s in slips)
    total_paid = sum(float(s["net_amount"]) for s in slips if s["status"] == "paid")
    pending = total_payroll - total_paid
    by_month: Dict[str, Dict[str, Any]] = {}
    for s in slips:
        key = f"{s['year']}-{s['month']:02d}"
        by_month.setdefault(key, {"month": key, "payroll": 0, "paid": 0})
        by_month[key]["payroll"] += float(s["net_amount"])
        if s["status"] == "paid":
            by_month[key]["paid"] += float(s["net_amount"])
    return {
        "total_payroll": round(total_payroll, 2),
        "total_paid": round(total_paid, 2),
        "total_pending": round(pending, 2),
        "by_month": sorted(by_month.values(), key=lambda x: x["month"]),
    }


# ─── Accounts (Chart of Accounts + Transactions) ──────────────────────────────
class AccountIn(BaseModel):
    name: str
    code: str
    type: str  # asset | liability | income | expense | equity
    description: Optional[str] = None


class TransactionIn(BaseModel):
    account_id: str
    type: str  # income | expense
    amount: float
    date: str  # YYYY-MM-DD
    description: Optional[str] = None
    category: Optional[str] = None
    reference: Optional[str] = None


@api.get("/accounts")
async def list_accounts(_: dict = Depends(get_current_user)):
    return await db.accounts.find({}, {"_id": 0}).sort("code", 1).to_list(500)


@api.post("/accounts")
async def create_account(data: AccountIn, _: dict = Depends(require_roles("admin"))):
    if data.type not in ("asset", "liability", "income", "expense", "equity"):
        raise HTTPException(400, "Invalid account type")
    if await db.accounts.find_one({"code": data.code}):
        raise HTTPException(400, "Account code already exists")
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.accounts.insert_one(doc.copy())
    return doc


@api.put("/accounts/{account_id}")
async def update_account(account_id: str, data: AccountIn, _: dict = Depends(require_roles("admin"))):
    if data.type not in ("asset", "liability", "income", "expense", "equity"):
        raise HTTPException(400, "Invalid account type")
    await db.accounts.update_one({"id": account_id}, {"$set": data.model_dump()})
    return await db.accounts.find_one({"id": account_id}, {"_id": 0})


@api.delete("/accounts/{account_id}")
async def delete_account(account_id: str, _: dict = Depends(require_roles("admin"))):
    if await db.transactions.find_one({"account_id": account_id}):
        raise HTTPException(400, "Account has transactions; cannot delete")
    await db.accounts.delete_one({"id": account_id})
    return {"ok": True}


@api.get("/transactions")
async def list_transactions(
    account_id: Optional[str] = None, type: Optional[str] = None,
    start: Optional[str] = None, end: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {}
    if account_id: flt["account_id"] = account_id
    if type: flt["type"] = type
    if start and end: flt["date"] = {"$gte": start, "$lte": end}
    items = await db.transactions.find(flt, {"_id": 0}).sort("date", -1).to_list(5000)
    acc_ids = list({t["account_id"] for t in items})
    accs = await db.accounts.find({"id": {"$in": acc_ids}}, {"_id": 0}).to_list(500)
    a_map = {a["id"]: a for a in accs}
    for t in items:
        a = a_map.get(t["account_id"], {})
        t["account_name"] = a.get("name")
        t["account_code"] = a.get("code")
    return items


@api.post("/transactions")
async def create_transaction(data: TransactionIn, _: dict = Depends(require_roles("admin"))):
    if data.type not in ("income", "expense"):
        raise HTTPException(400, "Invalid transaction type")
    if not await db.accounts.find_one({"id": data.account_id}):
        raise HTTPException(400, "Account not found")
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.transactions.insert_one(doc.copy())
    return doc


@api.delete("/transactions/{txn_id}")
async def delete_transaction(txn_id: str, _: dict = Depends(require_roles("admin"))):
    await db.transactions.delete_one({"id": txn_id})
    return {"ok": True}


@api.get("/accounts/statement")
async def account_statement(
    account_id: Optional[str] = None,
    start: Optional[str] = None, end: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {}
    if account_id: flt["account_id"] = account_id
    if start and end: flt["date"] = {"$gte": start, "$lte": end}
    txns = await db.transactions.find(flt, {"_id": 0}).sort("date", 1).to_list(20000)
    total_income = sum(float(t["amount"]) for t in txns if t["type"] == "income")
    total_expense = sum(float(t["amount"]) for t in txns if t["type"] == "expense")
    # running balance (income +, expense -)
    bal = 0
    for t in txns:
        bal += float(t["amount"]) if t["type"] == "income" else -float(t["amount"])
        t["running_balance"] = round(bal, 2)
    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net": round(total_income - total_expense, 2),
        "transactions": txns,
    }


# ─── Homework ─────────────────────────────────────────────────────────────────
class HomeworkIn(BaseModel):
    class_id: str
    subject_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    assigned_date: str
    due_date: str
    attachment_url: Optional[str] = None


@api.get("/homework")
async def list_homework(
    class_id: Optional[str] = None, subject_id: Optional[str] = None,
    active: Optional[bool] = None,
    _: dict = Depends(get_current_user),
):
    flt: Dict[str, Any] = {}
    if class_id: flt["class_id"] = class_id
    if subject_id: flt["subject_id"] = subject_id
    if active is True: flt["due_date"] = {"$gte": date.today().isoformat()}
    items = await db.homework.find(flt, {"_id": 0}).sort("due_date", -1).to_list(5000)
    cls_map = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    sub_map = {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for h in items:
        h["class_name"] = cls_map.get(h.get("class_id"))
        h["subject_name"] = sub_map.get(h.get("subject_id"))
    return items


@api.post("/homework")
async def create_homework(data: HomeworkIn, user: dict = Depends(require_roles("admin", "teacher"))):
    doc = {
        "id": gen_id(), **data.model_dump(),
        "created_by": user.get("id"), "created_at": iso(now_utc()),
    }
    await db.homework.insert_one(doc.copy())
    return doc


@api.put("/homework/{homework_id}")
async def update_homework(homework_id: str, data: HomeworkIn, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.homework.update_one({"id": homework_id}, {"$set": data.model_dump()})
    return await db.homework.find_one({"id": homework_id}, {"_id": 0})


@api.delete("/homework/{homework_id}")
async def delete_homework(homework_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.homework.delete_one({"id": homework_id})
    return {"ok": True}


# ─── Promote Students ─────────────────────────────────────────────────────────
class PromoteIn(BaseModel):
    from_class_id: str
    to_class_id: str
    student_ids: Optional[List[str]] = None  # if None, promote all in from_class


@api.post("/students/promote")
async def promote_students(data: PromoteIn, _: dict = Depends(require_roles("admin"))):
    if not await db.classes.find_one({"id": data.to_class_id}):
        raise HTTPException(400, "Target class not found")
    flt: Dict[str, Any] = {"class_id": data.from_class_id}
    if data.student_ids:
        flt["id"] = {"$in": data.student_ids}
    result = await db.students.update_many(flt, {"$set": {"class_id": data.to_class_id}})
    return {"promoted": result.modified_count}


# ─── PDF Exports ──────────────────────────────────────────────────────────────
from fastapi.responses import StreamingResponse
from io import BytesIO


def _pdf_response(buffer: BytesIO, filename: str):
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _build_pdf_header(institute: dict, title: str):
    """Returns reportlab elements for an institute-branded header."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer
    styles = getSampleStyleSheet()
    inst_name = (institute or {}).get("name") or "School"
    inst_tag = (institute or {}).get("tagline") or ""
    inst_addr = (institute or {}).get("address") or ""
    return [
        Paragraph(f"<b>{inst_name}</b>", ParagraphStyle("h", parent=styles["Title"], textColor="#4F46E5")),
        Paragraph(inst_tag, styles["Italic"]),
        Paragraph(inst_addr, styles["Normal"]),
        Spacer(1, 14),
        Paragraph(f"<b>{title}</b>", ParagraphStyle("sub", parent=styles["Heading2"])),
        Spacer(1, 10),
    ]


@api.get("/fees/invoices/{invoice_id}/slip.pdf")
async def fee_slip_pdf(invoice_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    inv = await db.fee_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    student = await db.students.find_one({"id": inv["student_id"]}, {"_id": 0}) or {}
    klass = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = _build_pdf_header(institute, "Fee Payment Receipt")
    styles = getSampleStyleSheet()
    MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    info = [
        ["Receipt #", inv["id"][:8].upper()],
        ["Student", student.get("name", "-")],
        ["Registration #", student.get("registration_number", "-")],
        ["Class", klass.get("name", "-")],
        ["Period", f"{MONTHS[inv['month']]} {inv['year']}"],
        ["Amount", f"${inv['amount']:,.2f}"],
        ["Paid", f"${(inv.get('paid_amount') or 0):,.2f}"],
        ["Status", inv["status"].upper()],
        ["Payment Method", (inv.get("payment_method") or "—").upper()],
        ["Paid Date", (inv.get("paid_date") or "")[:10] or "—"],
    ]
    t = Table(info, colWidths=[140, 320])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 22))
    elements.append(Paragraph("<i>This is a computer-generated receipt. No signature required.</i>", styles["Italic"]))
    doc.build(elements)
    return _pdf_response(buf, f"fee_slip_{invoice_id[:8]}.pdf")


@api.get("/salary/slips/{slip_id}/slip.pdf")
async def salary_slip_pdf(slip_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    slip = await db.salary_slips.find_one({"id": slip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(404, "Slip not found")
    emp = await db.employees.find_one({"id": slip["employee_id"]}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = _build_pdf_header(institute, "Salary Slip")
    styles = getSampleStyleSheet()
    MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    info = [
        ["Slip #", slip["id"][:8].upper()],
        ["Employee", emp.get("name", "-")],
        ["Role", (emp.get("role") or "-").replace("_", " ").title()],
        ["Period", f"{MONTHS[slip['month']]} {slip['year']}"],
        ["Base Salary", f"${slip['base_salary']:,.2f}"],
        ["Bonus", f"+ ${slip.get('bonus', 0):,.2f}"],
        ["Deductions", f"- ${slip.get('deductions', 0):,.2f}"],
        ["Net Payable", f"${slip['net_amount']:,.2f}"],
        ["Status", slip["status"].upper()],
        ["Paid Date", (slip.get("paid_date") or "")[:10] or "—"],
        ["Payment Method", (slip.get("payment_method") or "—").upper()],
    ]
    t = Table(info, colWidths=[140, 320])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 7), (-1, 7), "Helvetica-Bold"),
        ("BACKGROUND", (0, 7), (-1, 7), colors.HexColor("#EEF2FF")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 22))
    elements.append(Paragraph("<i>Computer-generated salary slip. No signature required.</i>", styles["Italic"]))
    doc.build(elements)
    return _pdf_response(buf, f"salary_slip_{slip_id[:8]}.pdf")


@api.get("/students/{student_id}/admission-letter.pdf")
async def admission_letter_pdf(student_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Student not found")
    klass = await db.classes.find_one({"id": s.get("class_id")}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    elements = _build_pdf_header(institute, "Admission Letter")
    styles = getSampleStyleSheet()
    today_s = date.today().strftime("%B %d, %Y")
    elements.append(Paragraph(f"Date: {today_s}", styles["Normal"]))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(f"Dear <b>{s.get('father_name') or 'Parent / Guardian'}</b>,", styles["Normal"]))
    elements.append(Spacer(1, 10))
    body = (
        f"We are delighted to inform you that <b>{s['name']}</b> "
        f"(Registration No. <b>{s['registration_number']}</b>) has been formally admitted to "
        f"<b>{klass.get('name', '—')}</b> at {(institute or {}).get('name', 'our institution')}."
    )
    elements.append(Paragraph(body, styles["BodyText"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "Admission is confirmed effective {ad}. We look forward to a wonderful academic journey ahead.".format(
            ad=(s.get("admission_date") or today_s)
        ),
        styles["BodyText"],
    ))
    elements.append(Spacer(1, 14))
    info = [
        ["Student Name", s.get("name", "-")],
        ["Registration #", s.get("registration_number", "-")],
        ["Class", klass.get("name", "-")],
        ["Admission Date", s.get("admission_date") or today_s],
        ["Father", s.get("father_name") or "-"],
        ["Mother", s.get("mother_name") or "-"],
        ["Contact", s.get("father_contact") or s.get("mother_contact") or s.get("mobile") or "-"],
        ["Address", s.get("address") or "-"],
    ]
    t = Table(info, colWidths=[140, 340])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 26))
    elements.append(Paragraph("Warm regards,", styles["Normal"]))
    elements.append(Paragraph(f"<b>The Principal</b><br/>{(institute or {}).get('name', '')}", styles["Normal"]))
    doc.build(elements)
    return _pdf_response(buf, f"admission_{s['registration_number']}.pdf")



# ─── Timetable ────────────────────────────────────────────────────────────────
class TimetableConfigIn(BaseModel):
    weekdays: List[str] = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    periods: List[Dict[str, str]] = []   # [{name, start, end}]
    classrooms: List[str] = []


class TimetableSlotIn(BaseModel):
    class_id: str
    weekday: str
    period_index: int
    subject_id: Optional[str] = None
    teacher_id: Optional[str] = None
    classroom: Optional[str] = None


@api.get("/timetable/config")
async def get_timetable_config(_: dict = Depends(get_current_user)):
    doc = await db.timetable_config.find_one({"id": "default"}, {"_id": 0})
    if not doc:
        doc = {
            "id": "default",
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "periods": [
                {"name": "P1", "start": "08:00", "end": "08:45"},
                {"name": "P2", "start": "08:50", "end": "09:35"},
                {"name": "P3", "start": "09:40", "end": "10:25"},
                {"name": "P4", "start": "10:45", "end": "11:30"},
                {"name": "P5", "start": "11:35", "end": "12:20"},
                {"name": "P6", "start": "13:00", "end": "13:45"},
            ],
            "classrooms": ["Room 101", "Room 102", "Room 103", "Lab A", "Lab B"],
        }
    return doc


@api.put("/timetable/config")
async def update_timetable_config(data: TimetableConfigIn, _: dict = Depends(require_roles("admin"))):
    upd = data.model_dump()
    upd["updated_at"] = iso(now_utc())
    await db.timetable_config.update_one({"id": "default"}, {"$set": upd, "$setOnInsert": {"id": "default"}}, upsert=True)
    return await db.timetable_config.find_one({"id": "default"}, {"_id": 0})


@api.get("/timetable")
async def get_timetable(class_id: Optional[str] = None, teacher_id: Optional[str] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if class_id: flt["class_id"] = class_id
    if teacher_id: flt["teacher_id"] = teacher_id
    slots = await db.timetable_slots.find(flt, {"_id": 0}).to_list(2000)
    subs = {s["id"]: s for s in await db.subjects.find({}, {"_id": 0}).to_list(500)}
    teachers = {e["id"]: e for e in await db.employees.find({}, {"_id": 0}).to_list(500)}
    classes = {c["id"]: c for c in await db.classes.find({}, {"_id": 0}).to_list(500)}
    for s in slots:
        s["subject_name"] = subs.get(s.get("subject_id"), {}).get("name")
        s["teacher_name"] = teachers.get(s.get("teacher_id"), {}).get("name")
        s["class_name"] = classes.get(s.get("class_id"), {}).get("name")
    return slots


@api.post("/timetable/slot")
async def upsert_timetable_slot(data: TimetableSlotIn, _: dict = Depends(require_roles("admin", "teacher"))):
    flt = {"class_id": data.class_id, "weekday": data.weekday, "period_index": data.period_index}
    update = data.model_dump()
    existing = await db.timetable_slots.find_one(flt)
    if existing:
        await db.timetable_slots.update_one({"id": existing["id"]}, {"$set": update})
        return await db.timetable_slots.find_one({"id": existing["id"]}, {"_id": 0})
    doc = {"id": gen_id(), **update, "created_at": iso(now_utc())}
    await db.timetable_slots.insert_one(doc.copy())
    return doc


@api.delete("/timetable/slot/{slot_id}")
async def delete_timetable_slot(slot_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.timetable_slots.delete_one({"id": slot_id})
    return {"ok": True}


# ─── Exams ────────────────────────────────────────────────────────────────────
class ExamIn(BaseModel):
    name: str
    class_id: str
    start_date: str
    end_date: str


class ExamSubjectIn(BaseModel):
    subject_id: str
    exam_date: str
    max_marks: float = 100
    pass_marks: float = 35


class ExamResultIn(BaseModel):
    student_id: str
    subject_id: str
    marks: float
    remarks: Optional[str] = None


@api.get("/exams")
async def list_exams(class_id: Optional[str] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if class_id: flt["class_id"] = class_id
    exams = await db.exams.find(flt, {"_id": 0}).sort("start_date", -1).to_list(500)
    cls = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for e in exams:
        e["class_name"] = cls.get(e.get("class_id"))
        e["subject_count"] = await db.exam_subjects.count_documents({"exam_id": e["id"]})
    return exams


@api.post("/exams")
async def create_exam(data: ExamIn, _: dict = Depends(require_roles("admin", "teacher"))):
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.exams.insert_one(doc.copy())
    return doc


@api.delete("/exams/{exam_id}")
async def delete_exam(exam_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.exams.delete_one({"id": exam_id})
    await db.exam_subjects.delete_many({"exam_id": exam_id})
    await db.exam_results.delete_many({"exam_id": exam_id})
    return {"ok": True}


@api.get("/exams/{exam_id}/subjects")
async def list_exam_subjects(exam_id: str, _: dict = Depends(get_current_user)):
    items = await db.exam_subjects.find({"exam_id": exam_id}, {"_id": 0}).sort("exam_date", 1).to_list(200)
    subs = {s["id"]: s for s in await db.subjects.find({}, {"_id": 0}).to_list(500)}
    for i in items:
        i["subject_name"] = subs.get(i.get("subject_id"), {}).get("name")
    return items


@api.post("/exams/{exam_id}/subjects")
async def add_exam_subject(exam_id: str, data: ExamSubjectIn, _: dict = Depends(require_roles("admin", "teacher"))):
    if not await db.exams.find_one({"id": exam_id}):
        raise HTTPException(404, "Exam not found")
    doc = {"id": gen_id(), "exam_id": exam_id, **data.model_dump(), "created_at": iso(now_utc())}
    await db.exam_subjects.insert_one(doc.copy())
    return doc


@api.delete("/exams/{exam_id}/subjects/{es_id}")
async def remove_exam_subject(exam_id: str, es_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.exam_subjects.delete_one({"id": es_id, "exam_id": exam_id})
    await db.exam_results.delete_many({"exam_id": exam_id, "subject_id": (await db.exam_subjects.find_one({"id": es_id}) or {}).get("subject_id")})
    return {"ok": True}


@api.get("/exams/{exam_id}/results")
async def list_exam_results(exam_id: str, student_id: Optional[str] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {"exam_id": exam_id}
    if student_id: flt["student_id"] = student_id
    results = await db.exam_results.find(flt, {"_id": 0}).to_list(20000)
    return results


@api.post("/exams/{exam_id}/results")
async def upsert_results(exam_id: str, results: List[ExamResultIn], _: dict = Depends(require_roles("admin", "teacher"))):
    saved = 0
    for r in results:
        flt = {"exam_id": exam_id, "student_id": r.student_id, "subject_id": r.subject_id}
        await db.exam_results.delete_many(flt)
        await db.exam_results.insert_one({"id": gen_id(), "exam_id": exam_id, **r.model_dump(), "created_at": iso(now_utc())})
        saved += 1
    return {"saved": saved}


def _grade_for(marks: float, max_marks: float, scale: List[Dict[str, Any]]) -> str:
    pct = (marks / max_marks) * 100 if max_marks else 0
    for tier in sorted(scale, key=lambda x: -float(x["min"])):
        if pct >= float(tier["min"]):
            return tier["grade"]
    return "—"


@api.get("/exams/{exam_id}/marksheet")
async def marksheet(exam_id: str, student_id: str, _: dict = Depends(get_current_user)):
    exam = await db.exams.find_one({"id": exam_id}, {"_id": 0})
    if not exam:
        raise HTTPException(404, "Exam not found")
    subjects = await db.exam_subjects.find({"exam_id": exam_id}, {"_id": 0}).to_list(200)
    sub_map = {s["id"]: s for s in await db.subjects.find({}, {"_id": 0}).to_list(500)}
    results = await db.exam_results.find({"exam_id": exam_id, "student_id": student_id}, {"_id": 0}).to_list(200)
    r_map = {r["subject_id"]: r for r in results}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    scale = (institute.get("grading_scale") or [
        {"grade": "A+", "min": 90}, {"grade": "A", "min": 80}, {"grade": "B", "min": 70},
        {"grade": "C", "min": 60}, {"grade": "D", "min": 50}, {"grade": "F", "min": 0},
    ])
    rows = []
    total_marks = 0.0
    total_max = 0.0
    for es in subjects:
        r = r_map.get(es["subject_id"])
        marks = float((r or {}).get("marks") or 0)
        rows.append({
            "subject_id": es["subject_id"],
            "subject_name": sub_map.get(es["subject_id"], {}).get("name"),
            "max_marks": es["max_marks"],
            "pass_marks": es["pass_marks"],
            "marks": marks if r else None,
            "grade": _grade_for(marks, es["max_marks"], scale) if r else None,
        })
        if r:
            total_marks += marks
            total_max += float(es["max_marks"])
    student = await db.students.find_one({"id": student_id}, {"_id": 0}) or {}
    return {
        "exam": exam,
        "student": student,
        "rows": rows,
        "total_marks": total_marks,
        "total_max": total_max,
        "percentage": round((total_marks / total_max * 100), 2) if total_max else 0,
        "overall_grade": _grade_for(total_marks, total_max or 1, scale) if total_max else "—",
    }


# ─── Question Papers ──────────────────────────────────────────────────────────
class QuestionPaperIn(BaseModel):
    title: str
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    duration_minutes: int = 60
    total_marks: int = 100
    instructions: Optional[str] = None
    questions: List[Dict[str, Any]] = []  # [{text, marks}]


@api.get("/question-papers")
async def list_qp(class_id: Optional[str] = None, subject_id: Optional[str] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if class_id: flt["class_id"] = class_id
    if subject_id: flt["subject_id"] = subject_id
    items = await db.question_papers.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
    cls = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    subs = {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for q in items:
        q["class_name"] = cls.get(q.get("class_id"))
        q["subject_name"] = subs.get(q.get("subject_id"))
    return items


@api.post("/question-papers")
async def create_qp(data: QuestionPaperIn, _: dict = Depends(require_roles("admin", "teacher"))):
    doc = {"id": gen_id(), **data.model_dump(), "created_at": iso(now_utc())}
    await db.question_papers.insert_one(doc.copy())
    return doc


@api.put("/question-papers/{qp_id}")
async def update_qp(qp_id: str, data: QuestionPaperIn, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.question_papers.update_one({"id": qp_id}, {"$set": data.model_dump()})
    return await db.question_papers.find_one({"id": qp_id}, {"_id": 0})


@api.delete("/question-papers/{qp_id}")
async def delete_qp(qp_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.question_papers.delete_one({"id": qp_id})
    return {"ok": True}


@api.get("/question-papers/{qp_id}/pdf")
async def qp_pdf(qp_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    qp = await db.question_papers.find_one({"id": qp_id}, {"_id": 0})
    if not qp:
        raise HTTPException(404, "Question paper not found")
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    cls = await db.classes.find_one({"id": qp.get("class_id")}, {"_id": 0}) or {}
    sub = await db.subjects.find_one({"id": qp.get("subject_id")}, {"_id": 0}) or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    elements = _build_pdf_header(institute, qp["title"])
    styles = getSampleStyleSheet()
    meta = (
        f"<b>Class:</b> {cls.get('name','—')} &nbsp;&nbsp; "
        f"<b>Subject:</b> {sub.get('name','—')} &nbsp;&nbsp; "
        f"<b>Duration:</b> {qp.get('duration_minutes')} min &nbsp;&nbsp; "
        f"<b>Total marks:</b> {qp.get('total_marks')}"
    )
    elements.append(Paragraph(meta, styles["Normal"]))
    elements.append(Spacer(1, 12))
    if qp.get("instructions"):
        elements.append(Paragraph(f"<i>Instructions:</i> {qp['instructions']}", styles["Italic"]))
        elements.append(Spacer(1, 10))
    for i, q in enumerate(qp.get("questions") or [], 1):
        elements.append(Paragraph(f"<b>Q{i}.</b> {q.get('text','')} &nbsp;&nbsp; <i>[{q.get('marks', '-')}M]</i>", styles["BodyText"]))
        elements.append(Spacer(1, 8))
    doc.build(elements)
    return _pdf_response(buf, f"qp_{qp_id[:8]}.pdf")


# ─── ID Cards & Letters & Certificates (PDFs) ─────────────────────────────────
def _draw_id_card(elements, institute, title, name, subtitle, info_rows):
    """Compact 1-page ID card layout."""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    styles = getSampleStyleSheet()
    inst_name = (institute or {}).get("name") or "School"
    elements.append(Paragraph(f"<b>{inst_name}</b>", ParagraphStyle("h", parent=styles["Title"], textColor="#4F46E5", alignment=1)))
    elements.append(Paragraph(title, ParagraphStyle("st", parent=styles["Heading3"], alignment=1, textColor="#475569")))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"<b>{name}</b>", ParagraphStyle("name", parent=styles["Heading1"], alignment=1)))
    elements.append(Paragraph(subtitle, ParagraphStyle("sub", parent=styles["Normal"], alignment=1, textColor="#64748B")))
    elements.append(Spacer(1, 18))
    t = Table(info_rows, colWidths=[140, 280])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)


@api.get("/students/{student_id}/id-card.pdf")
async def student_id_card(student_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A6, A4
    from reportlab.platypus import SimpleDocTemplate
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Student not found")
    cls = await db.classes.find_one({"id": s.get("class_id")}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=80, rightMargin=80, topMargin=80, bottomMargin=80)
    elements = []
    rows = [
        ["Registration #", s.get("registration_number", "-")],
        ["Class", cls.get("name", "-")],
        ["Blood Group", s.get("blood_group") or "-"],
        ["Contact", s.get("father_contact") or s.get("mobile") or "-"],
        ["DOB", s.get("dob") or "-"],
        ["Valid until", f"{date.today().year + 1}-03-31"],
    ]
    _draw_id_card(elements, institute, "STUDENT IDENTITY CARD", s["name"], s.get("gender") or "", rows)
    doc.build(elements)
    return _pdf_response(buf, f"student_id_{s['registration_number']}.pdf")


@api.get("/employees/{employee_id}/id-card.pdf")
async def employee_id_card(employee_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    e = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Employee not found")
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=80, rightMargin=80, topMargin=80, bottomMargin=80)
    elements = []
    rows = [
        ["Employee ID", e["id"][:8].upper()],
        ["Role", (e.get("role") or "").replace("_", " ").title()],
        ["Contact", e.get("contact") or e.get("email") or "-"],
        ["Joining Date", e.get("joining_date") or "-"],
        ["Valid until", f"{date.today().year + 1}-03-31"],
    ]
    _draw_id_card(elements, institute, "STAFF IDENTITY CARD", e["name"], (e.get("role") or "").replace("_", " ").title(), rows)
    doc.build(elements)
    return _pdf_response(buf, f"staff_id_{employee_id[:8]}.pdf")


@api.get("/employees/{employee_id}/job-letter.pdf")
async def employee_job_letter(employee_id: str, _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    e = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Employee not found")
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    elements = _build_pdf_header(institute, "Letter of Appointment")
    styles = getSampleStyleSheet()
    today_s = date.today().strftime("%B %d, %Y")
    elements.append(Paragraph(f"Date: {today_s}", styles["Normal"]))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(f"Dear <b>{e['name']}</b>,", styles["Normal"]))
    elements.append(Spacer(1, 10))
    role = (e.get("role") or "").replace("_", " ").title()
    body = (
        f"We are pleased to formally appoint you to the position of <b>{role}</b> at "
        f"{(institute or {}).get('name','our institution')} with effect from "
        f"<b>{e.get('joining_date') or today_s}</b>. Your monthly remuneration shall be "
        f"<b>${(e.get('monthly_salary') or 0):,.2f}</b>, subject to applicable deductions."
    )
    elements.append(Paragraph(body, styles["BodyText"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        "You are expected to uphold the institution's values of integrity, excellence and inclusivity. "
        "Your detailed terms of service are outlined in the staff handbook.",
        styles["BodyText"],
    ))
    elements.append(Spacer(1, 14))
    info = [
        ["Employee Name", e["name"]],
        ["Designation", role],
        ["Joining Date", e.get("joining_date") or "-"],
        ["Monthly Salary", f"${(e.get('monthly_salary') or 0):,.2f}"],
        ["Contact", e.get("contact") or e.get("email") or "-"],
    ]
    t = Table(info, colWidths=[140, 340])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 26))
    elements.append(Paragraph("Warm regards,", styles["Normal"]))
    elements.append(Paragraph(f"<b>The Principal</b><br/>{(institute or {}).get('name','')}", styles["Normal"]))
    doc.build(elements)
    return _pdf_response(buf, f"job_letter_{employee_id[:8]}.pdf")


_CERT_TEMPLATES = {
    "transfer": ("Transfer Certificate", (
        "This is to certify that <b>{name}</b>, son/daughter of "
        "<b>{father}</b>, bearing registration number <b>{reg}</b>, was a bona fide student of "
        "<b>{cls}</b> at {institute}. The student's conduct and character during their tenure with "
        "us have been satisfactory. We extend our best wishes for their future endeavours."
    )),
    "character": ("Character Certificate", (
        "This is to certify that <b>{name}</b> (Reg. <b>{reg}</b>, Class <b>{cls}</b>) bore an "
        "exemplary character during their association with {institute}. They were respectful, "
        "punctual and showed a strong sense of responsibility. We wish them every success."
    )),
    "completion": ("Course Completion Certificate", (
        "This is to certify that <b>{name}</b> (Reg. <b>{reg}</b>) has successfully completed "
        "the prescribed course of study for <b>{cls}</b> at {institute}. We commend their "
        "dedication and effort, and wish them success in their future pursuits."
    )),
    "admission": ("Admission Confirmation", (
        "This is to confirm that <b>{name}</b> (Reg. <b>{reg}</b>) has been admitted to "
        "<b>{cls}</b> at {institute} with effect from <b>{adm}</b>. We warmly welcome them to "
        "our academic community."
    )),
}


@api.get("/students/{student_id}/certificate.pdf")
async def student_certificate(student_id: str, type: str = "character", _: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    if type not in _CERT_TEMPLATES:
        raise HTTPException(400, f"Unknown certificate type: {type}")
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Student not found")
    cls = await db.classes.find_one({"id": s.get("class_id")}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    title, body_tpl = _CERT_TEMPLATES[type]
    body = body_tpl.format(
        name=s.get("name", "-"),
        father=s.get("father_name") or "-",
        reg=s.get("registration_number", "-"),
        cls=cls.get("name", "-"),
        institute=(institute or {}).get("name", "our institution"),
        adm=s.get("admission_date") or date.today().isoformat(),
    )
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=60, rightMargin=60, topMargin=70, bottomMargin=60)
    elements = _build_pdf_header(institute, title)
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Date: {date.today().strftime('%B %d, %Y')}", styles["Normal"]))
    elements.append(Spacer(1, 18))
    elements.append(Paragraph(body, ParagraphStyle("body", parent=styles["BodyText"], fontSize=12, leading=18)))
    elements.append(Spacer(1, 36))
    elements.append(Paragraph("___________________________", styles["Normal"]))
    elements.append(Paragraph("<b>The Principal</b>", styles["Normal"]))
    elements.append(Paragraph((institute or {}).get("name", ""), styles["Normal"]))
    doc.build(elements)
    return _pdf_response(buf, f"{type}_{s['registration_number']}.pdf")


# ─── Parent Portal ────────────────────────────────────────────────────────────
class ParentLinkIn(BaseModel):
    registration_number: str


@api.post("/parent/link-child")
async def link_child(data: ParentLinkIn, user: dict = Depends(require_roles("parent"))):
    student = await db.students.find_one({"registration_number": data.registration_number.strip()}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found with that registration number")
    linked = set(user.get("linked_student_ids") or [])
    linked.add(student["id"])
    await db.users.update_one({"id": user["id"]}, {"$set": {"linked_student_ids": list(linked)}})
    return {"linked_student_ids": list(linked), "student": student}


@api.post("/parent/unlink-child")
async def unlink_child(data: ParentLinkIn, user: dict = Depends(require_roles("parent"))):
    student = await db.students.find_one({"registration_number": data.registration_number.strip()}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    linked = [x for x in (user.get("linked_student_ids") or []) if x != student["id"]]
    await db.users.update_one({"id": user["id"]}, {"$set": {"linked_student_ids": linked}})
    return {"linked_student_ids": linked}


async def _ensure_parent_owns(user: dict, student_id: str):
    if student_id not in (user.get("linked_student_ids") or []):
        raise HTTPException(403, "Not linked to this child")


@api.get("/parent/children")
async def parent_children(user: dict = Depends(require_roles("parent"))):
    ids = user.get("linked_student_ids") or []
    if not ids:
        return []
    students = await db.students.find({"id": {"$in": ids}}, {"_id": 0}).to_list(50)
    cls_map = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for s in students:
        s["class_name"] = cls_map.get(s.get("class_id"))
    return students


@api.get("/parent/children/{student_id}/summary")
async def parent_child_summary(student_id: str, user: dict = Depends(require_roles("parent"))):
    await _ensure_parent_owns(user, student_id)
    today_iso = date.today().isoformat()
    month_start = today_iso[:7] + "-01"
    student = await db.students.find_one({"id": student_id}, {"_id": 0}) or {}
    klass = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0}) or {}
    # attendance (current month)
    att = await db.attendance.find(
        {"type": "student", "entity_id": student_id, "date": {"$gte": month_start, "$lte": today_iso}},
        {"_id": 0},
    ).to_list(200)
    att_counts = {"present": 0, "absent": 0, "late": 0, "leave": 0}
    for a in att:
        att_counts[a["status"]] = att_counts.get(a["status"], 0) + 1
    att_total = sum(att_counts.values())
    att_pct = round(att_counts["present"] / att_total * 100, 1) if att_total else 0
    # fees (this year)
    invs = await db.fee_invoices.find({"student_id": student_id, "year": date.today().year}, {"_id": 0}).sort("month", 1).to_list(50)
    total_due = sum(float(i["amount"]) for i in invs)
    paid = sum(float(i.get("paid_amount") or 0) for i in invs)
    # homework upcoming
    hw = await db.homework.find({"class_id": student.get("class_id"), "due_date": {"$gte": today_iso}}, {"_id": 0}).sort("due_date", 1).to_list(20)
    subs = {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for h in hw:
        h["subject_name"] = subs.get(h.get("subject_id"))
    return {
        "student": student,
        "class_name": klass.get("name"),
        "attendance": {"month_start": month_start, **att_counts, "total": att_total, "pct": att_pct},
        "fees": {"invoices": invs, "total_due": round(total_due, 2), "total_paid": round(paid, 2), "outstanding": round(total_due - paid, 2)},
        "upcoming_homework": hw,
    }






# ─── Stripe Payments (parent online fee payment) ──────────────────────────────
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)


class CheckoutStartIn(BaseModel):
    invoice_id: str
    origin_url: str


@api.post("/parent/fees/invoices/checkout")
async def parent_checkout(data: CheckoutStartIn, request: Request, user: dict = Depends(require_roles("parent"))):
    invoice = await db.fee_invoices.find_one({"id": data.invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice["student_id"] not in (user.get("linked_student_ids") or []):
        raise HTTPException(403, "Not linked to this child")
    if invoice["status"] == "paid":
        raise HTTPException(400, "Invoice already paid")
    outstanding = float(invoice["amount"]) - float(invoice.get("paid_amount") or 0)
    if outstanding <= 0:
        raise HTTPException(400, "Nothing to pay")

    api_key = os.environ["STRIPE_API_KEY"]
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    sc = StripeCheckout(api_key=api_key, webhook_url=webhook_url)

    origin = data.origin_url.rstrip("/")
    success_url = f"{origin}/parent?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/parent"
    metadata = {
        "invoice_id": invoice["id"],
        "student_id": invoice["student_id"],
        "parent_id": user["id"],
        "origin": "school_parent_portal",
    }
    req = CheckoutSessionRequest(
        amount=round(float(outstanding), 2), currency="usd",
        success_url=success_url, cancel_url=cancel_url, metadata=metadata,
    )
    session = await sc.create_checkout_session(req)

    await db.payment_transactions.insert_one({
        "id": gen_id(),
        "session_id": session.session_id,
        "invoice_id": invoice["id"],
        "student_id": invoice["student_id"],
        "parent_id": user["id"],
        "amount": round(float(outstanding), 2),
        "currency": "usd",
        "payment_status": "initiated",
        "status": "open",
        "metadata": metadata,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })
    return {"url": session.url, "session_id": session.session_id}


@api.get("/payments/checkout/status/{session_id}")
async def get_payment_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        raise HTTPException(404, "Payment session not found")
    if user.get("role") == "parent" and txn.get("parent_id") != user["id"]:
        raise HTTPException(403, "Not your payment session")

    # Try a live Stripe lookup; fall back to cached record if it fails (e.g. transient or proxy issue).
    payment_status = txn.get("payment_status") or "unpaid"
    session_status = txn.get("status") or "open"
    amount_total = int(round(float(txn.get("amount") or 0) * 100))
    currency = txn.get("currency") or "usd"
    try:
        api_key = os.environ["STRIPE_API_KEY"]
        host_url = str(request.base_url).rstrip("/")
        sc = StripeCheckout(api_key=api_key, webhook_url=f"{host_url}/api/webhook/stripe")
        status = await sc.get_checkout_status(session_id)
        payment_status = status.payment_status or payment_status
        session_status = status.status or session_status
        amount_total = status.amount_total if status.amount_total is not None else amount_total
        currency = status.currency or currency
    except Exception as e:
        logger.info(f"Stripe status lookup fell back to cache for {session_id}: {e}")

    if txn.get("payment_status") != "paid" and payment_status == "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "paid", "status": session_status, "updated_at": iso(now_utc())}},
        )
        inv = await db.fee_invoices.find_one({"id": txn["invoice_id"]}, {"_id": 0})
        if inv and inv.get("status") != "paid":
            new_paid = float(inv.get("paid_amount") or 0) + float(txn["amount"])
            await db.fee_invoices.update_one({"id": inv["id"]}, {"$set": {
                "paid_amount": new_paid,
                "status": "paid" if new_paid >= float(inv["amount"]) else "partial",
                "paid_date": iso(now_utc()),
                "payment_method": "stripe",
            }})
            fee_acct = await db.accounts.find_one({"code": "INC-FEE"})
            if fee_acct:
                await db.transactions.insert_one({
                    "id": gen_id(), "account_id": fee_acct["id"], "type": "income",
                    "amount": float(txn["amount"]),
                    "date": date.today().isoformat(),
                    "description": f"Online fee payment for invoice {inv['id'][:8]}",
                    "category": "fee", "reference": inv["id"],
                    "created_at": iso(now_utc()),
                })
    elif session_status == "expired":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "expired", "updated_at": iso(now_utc())}},
        )

    return {
        "session_id": session_id,
        "payment_status": payment_status,
        "status": session_status,
        "amount_total": amount_total,
        "currency": currency,
        "invoice_id": txn.get("invoice_id"),
    }


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    api_key = os.environ["STRIPE_API_KEY"]
    host_url = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=api_key, webhook_url=f"{host_url}/api/webhook/stripe")
    try:
        ev = await sc.handle_webhook(body, request.headers.get("Stripe-Signature"))
    except Exception as e:
        logger.warning(f"Stripe webhook error: {e}")
        return {"ok": False}
    # mirror status update on stored transaction (idempotent — also handled by polling)
    if ev.session_id:
        await db.payment_transactions.update_one(
            {"session_id": ev.session_id},
            {"$set": {"payment_status": ev.payment_status, "updated_at": iso(now_utc())}},
        )
    return {"ok": True}


# ─── Resend (email PDF delivery) ──────────────────────────────────────────────
class EmailPdfIn(BaseModel):
    recipient_email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None


def _resend_available() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip())


async def _send_pdf_email(to_email: str, subject: str, html_body: str, pdf_bytes: bytes, pdf_filename: str):
    import base64, asyncio, resend as _resend
    if not _resend_available():
        return {"status": "skipped", "reason": "RESEND_API_KEY not configured"}
    _resend.api_key = os.environ["RESEND_API_KEY"]
    params = {
        "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "attachments": [{
            "filename": pdf_filename,
            "content": base64.b64encode(pdf_bytes).decode("ascii"),
        }],
    }
    try:
        res = await asyncio.to_thread(_resend.Emails.send, params)
        return {"status": "sent", "id": (res or {}).get("id")}
    except Exception as e:
        logger.warning(f"Resend error: {e}")
        return {"status": "failed", "error": str(e)}


async def _build_fee_slip_pdf_bytes(invoice_id: str) -> tuple[bytes, str]:
    """Re-uses the slip generator logic — returns (bytes, filename)."""
    # Reuse logic from fee_slip_pdf by calling the function directly via DB
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    inv = await db.fee_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv: raise HTTPException(404, "Invoice not found")
    student = await db.students.find_one({"id": inv["student_id"]}, {"_id": 0}) or {}
    klass = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = _build_pdf_header(institute, "Fee Payment Receipt")
    styles = getSampleStyleSheet()
    MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    info = [
        ["Receipt #", inv["id"][:8].upper()],
        ["Student", student.get("name", "-")],
        ["Class", klass.get("name", "-")],
        ["Period", f"{MONTHS[inv['month']]} {inv['year']}"],
        ["Amount", f"${inv['amount']:,.2f}"],
        ["Paid", f"${(inv.get('paid_amount') or 0):,.2f}"],
        ["Status", inv["status"].upper()],
    ]
    t = Table(info, colWidths=[140, 320])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 22))
    elements.append(Paragraph("<i>This is a computer-generated receipt.</i>", styles["Italic"]))
    doc.build(elements)
    return buf.getvalue(), f"fee_slip_{invoice_id[:8]}.pdf"


@api.post("/fees/invoices/{invoice_id}/email")
async def email_fee_slip(invoice_id: str, data: EmailPdfIn, _: dict = Depends(require_roles("admin"))):
    pdf, fname = await _build_fee_slip_pdf_bytes(invoice_id)
    inv = await db.fee_invoices.find_one({"id": invoice_id}, {"_id": 0})
    student = await db.students.find_one({"id": inv["student_id"]}, {"_id": 0}) or {}
    subject = data.subject or f"Fee receipt for {student.get('name','-')}"
    msg = data.message or "Please find attached the fee receipt. Thank you."
    html = f"<p>{msg}</p><p><b>Receipt #{invoice_id[:8].upper()}</b> — ${inv['amount']:,.2f}</p>"
    res = await _send_pdf_email(data.recipient_email, subject, html, pdf, fname)
    await db.email_logs.insert_one({
        "id": gen_id(), "channel": "email", "recipient": data.recipient_email,
        "subject": subject, "ref": invoice_id, "ref_type": "fee_invoice",
        "status": res["status"], "error": res.get("error"), "sent_at": iso(now_utc()),
    })
    return res


@api.post("/salary/slips/{slip_id}/email")
async def email_salary_slip(slip_id: str, data: EmailPdfIn, _: dict = Depends(require_roles("admin"))):
    # build PDF via existing endpoint logic — duplicate small bit
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    slip = await db.salary_slips.find_one({"id": slip_id}, {"_id": 0})
    if not slip: raise HTTPException(404, "Slip not found")
    emp = await db.employees.find_one({"id": slip["employee_id"]}, {"_id": 0}) or {}
    institute = await db.institute.find_one({"id": "default"}, {"_id": 0}) or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = _build_pdf_header(institute, "Salary Slip")
    styles = getSampleStyleSheet()
    MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    info = [
        ["Employee", emp.get("name", "-")],
        ["Period", f"{MONTHS[slip['month']]} {slip['year']}"],
        ["Base", f"${slip['base_salary']:,.2f}"],
        ["Bonus", f"${slip.get('bonus',0):,.2f}"],
        ["Deductions", f"${slip.get('deductions',0):,.2f}"],
        ["Net Payable", f"${slip['net_amount']:,.2f}"],
        ["Status", slip["status"].upper()],
    ]
    t = Table(info, colWidths=[140, 320])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)
    doc.build(elements)
    pdf = buf.getvalue()
    subject = data.subject or f"Salary slip — {emp.get('name','-')} {MONTHS[slip['month']]} {slip['year']}"
    msg = data.message or "Please find attached your salary slip."
    html = f"<p>Dear {emp.get('name','-')},</p><p>{msg}</p>"
    res = await _send_pdf_email(data.recipient_email, subject, html, pdf, f"salary_slip_{slip_id[:8]}.pdf")
    await db.email_logs.insert_one({
        "id": gen_id(), "channel": "email", "recipient": data.recipient_email,
        "subject": subject, "ref": slip_id, "ref_type": "salary_slip",
        "status": res["status"], "error": res.get("error"), "sent_at": iso(now_utc()),
    })
    return res


@api.get("/emails/logs")
async def email_logs(_: dict = Depends(require_roles("admin"))):
    return await db.email_logs.find({}, {"_id": 0}).sort("sent_at", -1).limit(100).to_list(100)


# ─── User Management (admin) ──────────────────────────────────────────────────
class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    role: str  # admin|teacher|student|parent


class UserUpdateIn(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=8)


@api.get("/users")
async def list_users(role: Optional[str] = None, _: dict = Depends(require_roles("admin"))):
    flt: Dict[str, Any] = {}
    if role: flt["role"] = role
    users = await db.users.find(flt, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(2000)
    return users


@api.post("/users")
async def create_user(data: UserCreateIn, _: dict = Depends(require_roles("admin"))):
    if data.role not in ("admin", "teacher", "student", "parent"):
        raise HTTPException(400, "Invalid role")
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    doc = {
        "id": gen_id(), "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name, "role": data.role, "active": True,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc.copy())
    return clean(doc)


@api.put("/users/{user_id}")
async def update_user(user_id: str, data: UserUpdateIn, _: dict = Depends(require_roles("admin"))):
    upd = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if "role" in upd and upd["role"] not in ("admin", "teacher", "student", "parent"):
        raise HTTPException(400, "Invalid role")
    await db.users.update_one({"id": user_id}, {"$set": upd})
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


@api.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, data: PasswordResetIn, _: dict = Depends(require_roles("admin"))):
    if not await db.users.find_one({"id": user_id}):
        raise HTTPException(404, "User not found")
    await db.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_password(data.new_password)}})
    return {"ok": True}


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, current: dict = Depends(require_roles("admin"))):
    if user_id == current.get("id"):
        raise HTTPException(400, "Cannot delete your own account")
    await db.users.delete_one({"id": user_id})
    return {"ok": True}


# ─── Behaviour & Skills ───────────────────────────────────────────────────────
class RatingIn(BaseModel):
    student_id: str
    category: str
    rating: int = Field(ge=1, le=5)
    remark: Optional[str] = None
    date: Optional[str] = None


class ObservationIn(BaseModel):
    student_id: str
    note: str
    date: Optional[str] = None


def _ratings_routes(collection: str, kind: str):
    @api.get(f"/{kind}-ratings")
    async def _list(student_id: Optional[str] = None, _: dict = Depends(get_current_user)):
        flt: Dict[str, Any] = {}
        if student_id: flt["student_id"] = student_id
        return await db[collection].find(flt, {"_id": 0}).sort("date", -1).to_list(5000)

    @api.post(f"/{kind}-ratings")
    async def _create(data: RatingIn, user: dict = Depends(require_roles("admin", "teacher"))):
        doc = {
            "id": gen_id(), **data.model_dump(),
            "date": data.date or date.today().isoformat(),
            "rated_by": user.get("id"),
            "created_at": iso(now_utc()),
        }
        await db[collection].insert_one(doc.copy())
        return doc

    @api.delete(f"/{kind}-ratings/{{rating_id}}")
    async def _delete(rating_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
        await db[collection].delete_one({"id": rating_id})
        return {"ok": True}

    return _list, _create, _delete


# Register two parallel rating endpoints
_ratings_routes("behaviour_ratings", "behaviour")
_ratings_routes("skill_ratings", "skill")


@api.get("/observations")
async def list_observations(student_id: Optional[str] = None, _: dict = Depends(get_current_user)):
    flt: Dict[str, Any] = {}
    if student_id: flt["student_id"] = student_id
    items = await db.observations.find(flt, {"_id": 0}).sort("date", -1).to_list(5000)
    return items


@api.post("/observations")
async def create_observation(data: ObservationIn, user: dict = Depends(require_roles("admin", "teacher"))):
    doc = {
        "id": gen_id(), **data.model_dump(),
        "date": data.date or date.today().isoformat(),
        "observed_by": user.get("id"),
        "created_at": iso(now_utc()),
    }
    await db.observations.insert_one(doc.copy())
    return doc


@api.delete("/observations/{obs_id}")
async def delete_observation(obs_id: str, _: dict = Depends(require_roles("admin", "teacher"))):
    await db.observations.delete_one({"id": obs_id})
    return {"ok": True}



# ─── Dashboard / Reports ──────────────────────────────────────────────────────
@api.get("/dashboard/stats")
async def dashboard_stats(_: dict = Depends(get_current_user)):
    students = await db.students.count_documents({})
    employees = await db.employees.count_documents({})
    classes = await db.classes.count_documents({})
    subjects = await db.subjects.count_documents({})
    invs = await db.fee_invoices.find({}, {"_id": 0, "amount": 1, "paid_amount": 1, "status": 1}).to_list(20000)
    total_billed = sum(float(i["amount"]) for i in invs)
    total_collected = sum(float(i.get("paid_amount") or 0) for i in invs)
    pending_invoices = sum(1 for i in invs if i["status"] != "paid")

    # Attendance today
    today = date.today().isoformat()
    today_records = await db.attendance.find({"type": "student", "date": today}, {"_id": 0}).to_list(10000)
    present_today = sum(1 for r in today_records if r["status"] == "present")
    total_today = len(today_records)
    attendance_pct = round((present_today / total_today * 100), 1) if total_today else 0

    # Recent activity (latest 5 students)
    recent_students = await db.students.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    recent_payments = await db.fee_invoices.find({"status": {"$in": ["paid", "partial"]}}, {"_id": 0}).sort("paid_date", -1).limit(5).to_list(5)

    return {
        "students": students,
        "employees": employees,
        "classes": classes,
        "subjects": subjects,
        "total_billed": round(total_billed, 2),
        "total_collected": round(total_collected, 2),
        "pending_invoices": pending_invoices,
        "attendance_pct": attendance_pct,
        "present_today": present_today,
        "total_marked_today": total_today,
        "recent_students": recent_students,
        "recent_payments": recent_payments,
    }


# ─── Seed ─────────────────────────────────────────────────────────────────────
SEED_STUDENT_NAMES = [
    "Aarav Sharma", "Saanvi Iyer", "Vihaan Patel", "Anika Reddy", "Aditya Gupta",
    "Diya Verma", "Arjun Mehta", "Ishita Kapoor", "Reyansh Singh", "Myra Joshi",
    "Kabir Nair", "Anya Bose", "Rudra Pillai", "Tara Menon", "Atharv Rao",
    "Kiara Dutta", "Veer Banerjee", "Pari Chakraborty", "Ayaan Kulkarni", "Zara Khanna",
]

SEED_EMPLOYEES = [
    ("Dr. Priya Iyer", "principal", 120000, "priya.iyer@school.com"),
    ("Rahul Khanna", "vice_principal", 90000, "rahul.k@school.com"),
    ("Anita Desai", "teacher", 55000, "anita.d@school.com"),
    ("Suresh Menon", "teacher", 58000, "suresh.m@school.com"),
    ("Kavita Rao", "teacher", 52000, "kavita.r@school.com"),
    ("Vikram Singh", "teacher", 60000, "vikram.s@school.com"),
    ("Neha Banerjee", "teacher", 54000, "neha.b@school.com"),
    ("Amit Kumar", "accountant", 45000, "amit.k@school.com"),
    ("Sunita Joshi", "librarian", 38000, "sunita.j@school.com"),
    ("Ramesh Pillai", "support_staff", 25000, "ramesh.p@school.com"),
]


async def seed_initial_data():
    # Admin
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": gen_id(),
            "email": admin_email,
            "password_hash": hash_password(admin_pw),
            "name": "School Administrator",
            "role": "admin",
            "created_at": iso(now_utc()),
        })
        logger.info(f"Seeded admin user: {admin_email}")
    elif not verify_password(admin_pw, existing.get("password_hash", "")):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_pw)}})

    # Demo teacher
    teacher_email = "teacher@school.com"
    if not await db.users.find_one({"email": teacher_email}):
        await db.users.insert_one({
            "id": gen_id(), "email": teacher_email,
            "password_hash": hash_password("teacher123"),
            "name": "Demo Teacher", "role": "teacher",
            "created_at": iso(now_utc()),
        })

    # Institute
    if not await db.institute.find_one({"id": "default"}):
        await db.institute.insert_one({
            "id": "default",
            "name": "Greenwood International School",
            "tagline": "Nurturing curious minds since 1998",
            "logo_url": "",
            "phone": "+1 (555) 010-2030",
            "website": "https://greenwoodschool.edu",
            "address": "221B Baker Street, Springfield",
            "county": "Westfield County",
            "email": "info@greenwoodschool.edu",
            "rules": "Punctuality, respect, and integrity guide every Greenwood scholar.",
            "grading_scale": [
                {"grade": "A+", "min": 90}, {"grade": "A", "min": 80},
                {"grade": "B", "min": 70}, {"grade": "C", "min": 60},
                {"grade": "D", "min": 50}, {"grade": "F", "min": 0},
            ],
            "discount_types": ["Sibling", "Merit", "Staff Ward", "Need-based"],
            "fee_particulars": ["Tuition", "Transport", "Lab", "Library", "Sports"],
            "created_at": iso(now_utc()),
        })

    # Employees
    employee_ids: List[str] = []
    if await db.employees.count_documents({}) == 0:
        for idx, (name, role, salary, email) in enumerate(SEED_EMPLOYEES):
            eid = gen_id()
            employee_ids.append(eid)
            await db.employees.insert_one({
                "id": eid, "name": name, "role": role, "contact": f"+155500{1000+idx:04d}",
                "monthly_salary": salary, "email": email, "joining_date": "2020-06-15",
                "education": "M.A. / B.Ed.", "experience": f"{5 + idx} years",
                "gender": "Female" if idx % 2 == 0 else "Male",
                "dob": "1985-04-12", "address": "Faculty Quarters, Greenwood Campus",
                "pan": f"ABCDE{1234+idx}F", "spouse_name": None, "picture_url": None,
                "created_at": iso(now_utc()),
            })
    else:
        employee_ids = [e["id"] for e in await db.employees.find({}, {"_id": 0, "id": 1}).to_list(100)]

    # Classes
    class_ids: List[str] = []
    if await db.classes.count_documents({}) == 0:
        teacher_pool = [e for e in employee_ids[2:7]]  # teachers
        class_specs = [("Grade 1", 4500), ("Grade 2", 4800), ("Grade 3", 5200), ("Grade 4", 5500), ("Grade 5", 5800)]
        for i, (name, fee) in enumerate(class_specs):
            cid = gen_id()
            class_ids.append(cid)
            await db.classes.insert_one({
                "id": cid, "name": name, "monthly_fee": fee,
                "class_teacher_id": teacher_pool[i % len(teacher_pool)] if teacher_pool else None,
                "section": "A", "created_at": iso(now_utc()),
            })
    else:
        class_ids = [c["id"] for c in await db.classes.find({}, {"_id": 0, "id": 1}).to_list(100)]

    # Subjects
    if await db.subjects.count_documents({}) == 0:
        for name, code in [
            ("English", "ENG"), ("Mathematics", "MATH"), ("Science", "SCI"),
            ("Social Studies", "SOC"), ("Computer Science", "CS"), ("Art & Craft", "ART"),
        ]:
            await db.subjects.insert_one({
                "id": gen_id(), "name": name, "code": code,
                "class_ids": class_ids, "created_at": iso(now_utc()),
            })

    # Students
    if await db.students.count_documents({}) == 0:
        for i, name in enumerate(SEED_STUDENT_NAMES):
            cid = class_ids[i % len(class_ids)] if class_ids else None
            await db.students.insert_one({
                "id": gen_id(),
                "name": name,
                "registration_number": f"GW2025{1001+i:04d}",
                "class_id": cid,
                "picture_url": None,
                "admission_date": "2025-04-01",
                "fee_discount": 200 if i % 5 == 0 else 0,
                "mobile": f"+155500{2000+i:04d}",
                "dob": f"201{4+(i%6)}-0{1+(i%9)}-1{i%9}",
                "gender": "Female" if i % 2 == 0 else "Male",
                "cast": "General",
                "identification_marks": "",
                "previous_school": "Little Stars Pre-School",
                "religion": "Not specified",
                "blood_group": ["O+", "A+", "B+", "AB+"][i % 4],
                "address": f"{100+i} Maple Avenue, Springfield",
                "additional_note": "",
                "father_name": f"Mr. {name.split()[1]}",
                "father_contact": f"+155500{3000+i:04d}",
                "mother_name": f"Mrs. {name.split()[1]}",
                "mother_contact": f"+155500{4000+i:04d}",
                "created_at": iso(now_utc()),
            })

    # Fee invoices for current month
    if await db.fee_invoices.count_documents({}) == 0:
        today = date.today()
        students = await db.students.find({}, {"_id": 0}).to_list(1000)
        cls_map = {c["id"]: c for c in await db.classes.find({}, {"_id": 0}).to_list(100)}
        for i, s in enumerate(students):
            c = cls_map.get(s.get("class_id"))
            base = float((c or {}).get("monthly_fee") or 0)
            discount = float(s.get("fee_discount") or 0)
            amt = max(0, base - discount)
            paid = amt if i % 3 == 0 else (amt / 2 if i % 4 == 0 else 0)
            status = "paid" if paid >= amt else ("partial" if paid > 0 else "pending")
            await db.fee_invoices.insert_one({
                "id": gen_id(), "student_id": s["id"], "month": today.month, "year": today.year,
                "amount": amt, "paid_amount": paid, "status": status,
                "due_date": today.replace(day=10).isoformat(),
                "paid_date": iso(now_utc()) if paid > 0 else None,
                "payment_method": "cash" if paid > 0 else None,
                "notes": None, "created_at": iso(now_utc()),
            })

    # Attendance today
    if await db.attendance.count_documents({"date": date.today().isoformat()}) == 0:
        students = await db.students.find({}, {"_id": 0}).to_list(1000)
        today_iso = date.today().isoformat()
        for i, s in enumerate(students):
            status = "present" if i % 7 != 0 else ("absent" if i % 14 == 0 else "late")
            await db.attendance.insert_one({
                "id": gen_id(), "type": "student", "entity_id": s["id"],
                "class_id": s.get("class_id"), "date": today_iso, "status": status,
                "notes": None, "created_at": iso(now_utc()),
            })

    # Chart of accounts (seed defaults)
    if await db.accounts.count_documents({}) == 0:
        defaults = [
            ("INC-FEE", "Tuition Fees", "income", "Collected school fees"),
            ("INC-MISC", "Miscellaneous Income", "income", "Donations, events, etc."),
            ("EXP-SAL", "Salaries", "expense", "Staff salaries"),
            ("EXP-UTIL", "Utilities", "expense", "Electricity, water, internet"),
            ("EXP-SUPPLY", "Supplies", "expense", "Stationery, lab materials"),
            ("EXP-MAINT", "Maintenance", "expense", "Building upkeep"),
            ("ASSET-CASH", "Cash on Hand", "asset", "Petty cash"),
            ("ASSET-BANK", "Bank Account", "asset", "Operational bank balance"),
        ]
        for code, name, typ, desc in defaults:
            await db.accounts.insert_one({
                "id": gen_id(), "code": code, "name": name, "type": typ,
                "description": desc, "created_at": iso(now_utc()),
            })

    # Sample transactions
    if await db.transactions.count_documents({}) == 0:
        today_iso = date.today().isoformat()
        util_acct = await db.accounts.find_one({"code": "EXP-UTIL"}, {"_id": 0})
        supply_acct = await db.accounts.find_one({"code": "EXP-SUPPLY"}, {"_id": 0})
        misc_acct = await db.accounts.find_one({"code": "INC-MISC"}, {"_id": 0})
        if util_acct:
            await db.transactions.insert_one({
                "id": gen_id(), "account_id": util_acct["id"], "type": "expense",
                "amount": 2400, "date": today_iso, "description": "Monthly utilities",
                "category": "utility", "reference": None, "created_at": iso(now_utc()),
            })
        if supply_acct:
            await db.transactions.insert_one({
                "id": gen_id(), "account_id": supply_acct["id"], "type": "expense",
                "amount": 850, "date": today_iso, "description": "Lab supplies",
                "category": "supply", "reference": None, "created_at": iso(now_utc()),
            })
        if misc_acct:
            await db.transactions.insert_one({
                "id": gen_id(), "account_id": misc_acct["id"], "type": "income",
                "amount": 1500, "date": today_iso, "description": "Annual day donations",
                "category": "donation", "reference": None, "created_at": iso(now_utc()),
            })

    # Salary slips for current month
    if await db.salary_slips.count_documents({}) == 0:
        today = date.today()
        emps = await db.employees.find({}, {"_id": 0}).to_list(500)
        for i, e in enumerate(emps):
            base = float(e.get("monthly_salary") or 0)
            paid = i % 2 == 0
            await db.salary_slips.insert_one({
                "id": gen_id(), "employee_id": e["id"],
                "month": today.month, "year": today.year,
                "base_salary": base, "bonus": 0, "deductions": 0,
                "net_amount": base,
                "status": "paid" if paid else "pending",
                "paid_date": iso(now_utc()) if paid else None,
                "payment_method": "bank" if paid else None,
                "notes": None, "created_at": iso(now_utc()),
            })

    # Homework sample
    if await db.homework.count_documents({}) == 0:
        classes = await db.classes.find({}, {"_id": 0}).to_list(50)
        subjects = await db.subjects.find({}, {"_id": 0}).to_list(50)
        today = date.today()
        samples = [
            ("Read Chapter 3", "Read chapter 3 of the English textbook and answer comprehension Q1-Q5."),
            ("Math worksheet", "Complete fractions worksheet — questions 1 through 12."),
            ("Science diagram", "Draw and label parts of a plant cell."),
        ]
        for i, (title, desc) in enumerate(samples):
            if i >= len(classes):
                break
            await db.homework.insert_one({
                "id": gen_id(),
                "class_id": classes[i]["id"],
                "subject_id": subjects[i % len(subjects)]["id"] if subjects else None,
                "title": title, "description": desc,
                "assigned_date": today.isoformat(),
                "due_date": (today + timedelta(days=7)).isoformat(),
                "attachment_url": None, "created_by": "system",
                "created_at": iso(now_utc()),
            })

    # Timetable config (default)
    if not await db.timetable_config.find_one({"id": "default"}):
        await db.timetable_config.insert_one({
            "id": "default",
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "periods": [
                {"name": "P1", "start": "08:00", "end": "08:45"},
                {"name": "P2", "start": "08:50", "end": "09:35"},
                {"name": "P3", "start": "09:40", "end": "10:25"},
                {"name": "P4", "start": "10:45", "end": "11:30"},
                {"name": "P5", "start": "11:35", "end": "12:20"},
                {"name": "P6", "start": "13:00", "end": "13:45"},
            ],
            "classrooms": ["Room 101", "Room 102", "Room 103", "Lab A", "Lab B"],
            "created_at": iso(now_utc()),
        })

    # Sample timetable slots for first class
    if await db.timetable_slots.count_documents({}) == 0:
        first_class = await db.classes.find_one({}, {"_id": 0})
        subjects = await db.subjects.find({}, {"_id": 0}).to_list(20)
        teachers = await db.employees.find({"role": "teacher"}, {"_id": 0}).to_list(10)
        if first_class and subjects and teachers:
            days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            for d_i, day in enumerate(days):
                for p in range(6):
                    sub = subjects[(d_i * 6 + p) % len(subjects)]
                    teacher = teachers[(d_i * 6 + p) % len(teachers)]
                    await db.timetable_slots.insert_one({
                        "id": gen_id(),
                        "class_id": first_class["id"],
                        "weekday": day,
                        "period_index": p,
                        "subject_id": sub["id"],
                        "teacher_id": teacher["id"],
                        "classroom": ["Room 101", "Room 102", "Lab A"][p % 3],
                        "created_at": iso(now_utc()),
                    })

    # Sample exam with subjects
    if await db.exams.count_documents({}) == 0:
        first_class = await db.classes.find_one({}, {"_id": 0})
        subjects = await db.subjects.find({}, {"_id": 0}).to_list(10)
        if first_class and subjects:
            today = date.today()
            exam_id = gen_id()
            await db.exams.insert_one({
                "id": exam_id, "name": "Mid-Term Examination",
                "class_id": first_class["id"],
                "start_date": (today + timedelta(days=14)).isoformat(),
                "end_date": (today + timedelta(days=20)).isoformat(),
                "created_at": iso(now_utc()),
            })
            for i, sub in enumerate(subjects[:5]):
                await db.exam_subjects.insert_one({
                    "id": gen_id(), "exam_id": exam_id,
                    "subject_id": sub["id"],
                    "exam_date": (today + timedelta(days=14 + i)).isoformat(),
                    "max_marks": 100, "pass_marks": 35,
                    "created_at": iso(now_utc()),
                })

    # Sample question paper
    if await db.question_papers.count_documents({}) == 0:
        first_class = await db.classes.find_one({}, {"_id": 0})
        first_sub = await db.subjects.find_one({}, {"_id": 0})
        if first_class and first_sub:
            await db.question_papers.insert_one({
                "id": gen_id(),
                "title": f"Sample Mid-Term Paper — {first_sub['name']}",
                "subject_id": first_sub["id"],
                "class_id": first_class["id"],
                "duration_minutes": 90,
                "total_marks": 50,
                "instructions": "Answer all questions. Show your working. Calculators are not permitted.",
                "questions": [
                    {"text": "Define and give one example of a primary source.", "marks": 5},
                    {"text": "Solve: 7 × (12 + 3) - 18 ÷ 2.", "marks": 5},
                    {"text": "Write a short paragraph (4–5 sentences) about your favourite season.", "marks": 10},
                    {"text": "Label the parts of a plant cell in the diagram below.", "marks": 10},
                    {"text": "List two causes and two effects of deforestation.", "marks": 10},
                    {"text": "In your own words, explain Newton's first law of motion.", "marks": 10},
                ],
                "created_at": iso(now_utc()),
            })

    # Sample parent user linked to first 2 students
    parent_email = "parent@school.com"
    if not await db.users.find_one({"email": parent_email}):
        sample_students = await db.students.find({}, {"_id": 0, "id": 1}).limit(2).to_list(2)
        await db.users.insert_one({
            "id": gen_id(), "email": parent_email,
            "password_hash": hash_password("parent123"),
            "name": "Demo Parent", "role": "parent",
            "linked_student_ids": [s["id"] for s in sample_students],
            "created_at": iso(now_utc()),
        })






@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.students.create_index("registration_number", unique=True)
    await db.classes.create_index("name")
    await seed_initial_data()
    # write test credentials
    creds_path = Path("/app/memory/test_credentials.md")
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(
        "# Test Credentials\n\n"
        "## Admin\n"
        f"- Email: `{os.environ['ADMIN_EMAIL']}`\n"
        f"- Password: `{os.environ['ADMIN_PASSWORD']}`\n"
        "- Role: admin\n\n"
        "## Teacher (demo)\n"
        "- Email: `teacher@school.com`\n"
        "- Password: `teacher123`\n"
        "- Role: teacher\n\n"
        "## Parent (demo)\n"
        "- Email: `parent@school.com`\n"
        "- Password: `parent123`\n"
        "- Role: parent (linked to first 2 seeded students)\n\n"
        "## Auth endpoints\n"
        "- POST /api/auth/login\n"
        "- POST /api/auth/register\n"
        "- POST /api/auth/logout\n"
        "- GET  /api/auth/me\n"
    )
    logger.info("Startup complete: indexes + seed data ready")


@app.on_event("shutdown")
async def shutdown():
    client.close()


@api.get("/")
async def root():
    return {"app": "School Management System", "status": "ok"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
