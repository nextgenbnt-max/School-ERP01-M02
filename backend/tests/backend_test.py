"""Backend regression tests for School Management System."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://edumanage-core-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@school.com", "password": "admin123"}
TEACHER = {"email": "teacher@school.com", "password": "teacher123"}


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def teacher_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=TEACHER, timeout=30)
    assert r.status_code == 200, f"teacher login failed: {r.status_code} {r.text}"
    return s


# ─── Auth ─────────────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_success_sets_cookies(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["email"] == ADMIN["email"]
        assert data["user"]["role"] == "admin"
        assert "access_token" in s.cookies
        assert "refresh_token" in s.cookies

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN["email"], "password": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_me_without_cookie(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        r = s.post(f"{API}/auth/logout", timeout=30)
        assert r.status_code == 200
        # After logout cookies should be cleared - test by calling /me
        r2 = requests.get(f"{API}/auth/me", cookies={}, timeout=30)
        assert r2.status_code == 401


# ─── Dashboard / Institute ────────────────────────────────────────────────────
class TestDashboardInstitute:
    def test_dashboard_stats(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/stats", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("students", "employees", "classes", "subjects"):
            assert k in d
        assert d["students"] >= 20
        assert d["employees"] >= 10
        assert d["classes"] >= 5
        assert d["subjects"] >= 6

    def test_get_institute(self, admin_session):
        r = admin_session.get(f"{API}/institute", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "Greenwood" in (d.get("name") or "")

    def test_update_institute_admin(self, admin_session):
        new_tag = f"Updated tag {int(time.time())}"
        r = admin_session.put(f"{API}/institute", json={"tagline": new_tag}, timeout=30)
        assert r.status_code == 200
        assert r.json()["tagline"] == new_tag
        # verify persistence
        r2 = admin_session.get(f"{API}/institute", timeout=30)
        assert r2.json()["tagline"] == new_tag

    def test_update_institute_teacher_forbidden(self, teacher_session):
        r = teacher_session.put(f"{API}/institute", json={"tagline": "hacked"}, timeout=30)
        assert r.status_code == 403


# ─── Classes / Subjects ───────────────────────────────────────────────────────
class TestClasses:
    def test_list_classes(self, admin_session):
        r = admin_session.get(f"{API}/classes", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 5
        assert all("student_count" in c for c in items)

    def test_class_crud(self, admin_session):
        # create
        r = admin_session.post(f"{API}/classes", json={"name": "TEST_Class", "monthly_fee": 1000}, timeout=30)
        assert r.status_code == 200
        cid = r.json()["id"]
        # update
        r = admin_session.put(f"{API}/classes/{cid}", json={"name": "TEST_Class_Edit", "monthly_fee": 1500}, timeout=30)
        assert r.status_code == 200
        assert r.json()["monthly_fee"] == 1500
        # delete
        r = admin_session.delete(f"{API}/classes/{cid}", timeout=30)
        assert r.status_code == 200

    def test_teacher_cannot_delete_class(self, admin_session, teacher_session):
        r = admin_session.post(f"{API}/classes", json={"name": "TEST_RoleClass", "monthly_fee": 0}, timeout=30)
        cid = r.json()["id"]
        r2 = teacher_session.delete(f"{API}/classes/{cid}", timeout=30)
        assert r2.status_code == 403
        # cleanup
        admin_session.delete(f"{API}/classes/{cid}", timeout=30)


class TestSubjects:
    def test_subjects_crud(self, admin_session):
        r = admin_session.get(f"{API}/subjects", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 6
        c = admin_session.post(f"{API}/subjects", json={"name": "TEST_Subj", "code": "TST"}, timeout=30)
        assert c.status_code == 200
        sid = c.json()["id"]
        u = admin_session.put(f"{API}/subjects/{sid}", json={"name": "TEST_Subj2", "code": "TS2"}, timeout=30)
        assert u.status_code == 200
        d = admin_session.delete(f"{API}/subjects/{sid}", timeout=30)
        assert d.status_code == 200


# ─── Students ─────────────────────────────────────────────────────────────────
class TestStudents:
    def test_list_students_and_filter(self, admin_session):
        r = admin_session.get(f"{API}/students", timeout=30)
        assert r.status_code == 200
        students = r.json()
        assert len(students) >= 20
        # filter by q
        r2 = admin_session.get(f"{API}/students", params={"q": "Aarav"}, timeout=30)
        assert r2.status_code == 200
        assert any("Aarav" in s["name"] for s in r2.json())

    def test_create_student_unique_reg(self, admin_session):
        reg = f"TEST_REG_{int(time.time())}"
        r = admin_session.post(f"{API}/students", json={"name": "TEST_Stud", "registration_number": reg}, timeout=30)
        assert r.status_code == 200
        sid = r.json()["id"]
        # duplicate
        r2 = admin_session.post(f"{API}/students", json={"name": "TEST_Dup", "registration_number": reg}, timeout=30)
        assert r2.status_code == 400
        # cleanup
        admin_session.delete(f"{API}/students/{sid}", timeout=30)


# ─── Employees ────────────────────────────────────────────────────────────────
class TestEmployees:
    def test_employees_crud(self, admin_session):
        r = admin_session.get(f"{API}/employees", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 10
        c = admin_session.post(f"{API}/employees", json={"name": "TEST_Emp", "role": "teacher"}, timeout=30)
        assert c.status_code == 200
        eid = c.json()["id"]
        u = admin_session.put(f"{API}/employees/{eid}", json={"name": "TEST_Emp2", "role": "teacher"}, timeout=30)
        assert u.status_code == 200
        assert u.json()["name"] == "TEST_Emp2"
        d = admin_session.delete(f"{API}/employees/{eid}", timeout=30)
        assert d.status_code == 200


# ─── Fees ─────────────────────────────────────────────────────────────────────
class TestFees:
    def test_list_invoices(self, admin_session):
        r = admin_session.get(f"{API}/fees/invoices", timeout=30)
        assert r.status_code == 200

    def test_bulk_generate_and_pay(self, admin_session):
        # Use far future month to avoid clashing
        r = admin_session.post(f"{API}/fees/invoices/bulk-generate", params={"month": 11, "year": 2099}, timeout=60)
        assert r.status_code == 200
        created = r.json().get("created", 0)
        assert created >= 0
        # list those invoices
        r2 = admin_session.get(f"{API}/fees/invoices", params={"month": 11, "year": 2099}, timeout=30)
        assert r2.status_code == 200
        invs = r2.json()
        if invs:
            inv = next((i for i in invs if i["amount"] > 0 and i["status"] == "pending"), invs[0])
            iid = inv["id"]
            r3 = admin_session.post(f"{API}/fees/invoices/{iid}/pay", json={"paid_amount": inv["amount"], "payment_method": "cash"}, timeout=30)
            assert r3.status_code == 200
            assert r3.json()["status"] == "paid"

    def test_fees_report(self, admin_session):
        r = admin_session.get(f"{API}/fees/report", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_billed", "total_collected", "total_pending", "by_month"):
            assert k in d


# ─── Attendance ───────────────────────────────────────────────────────────────
class TestAttendance:
    def test_mark_and_get(self, admin_session):
        students = admin_session.get(f"{API}/students", timeout=30).json()
        assert students
        sid = students[0]["id"]
        cid = students[0].get("class_id")
        payload = {
            "type": "student", "date": "2099-01-15", "class_id": cid,
            "records": [{"entity_id": sid, "status": "present"}],
        }
        r = admin_session.post(f"{API}/attendance/mark", json=payload, timeout=30)
        assert r.status_code == 200
        r2 = admin_session.get(f"{API}/attendance", params={"type": "student", "date": "2099-01-15"}, timeout=30)
        assert r2.status_code == 200
        assert any(a["entity_id"] == sid for a in r2.json())

    def test_attendance_report(self, admin_session):
        r = admin_session.get(f"{API}/attendance/report", params={"type": "student"}, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ─── Messages ─────────────────────────────────────────────────────────────────
class TestMessages:
    def test_send_skipped_when_twilio_blank(self, admin_session):
        r = admin_session.post(f"{API}/messages/send", json={"channel": "sms", "recipients": ["+15555550001"], "body": "test"}, timeout=30)
        assert r.status_code == 200, f"send failed: {r.text}"
        d = r.json()
        assert d["results"][0]["status"] == "skipped"
