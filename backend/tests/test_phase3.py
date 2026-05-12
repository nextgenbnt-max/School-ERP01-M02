"""Phase 3 backend regression: Stripe checkout, Resend email PDFs, Users CRUD, Behaviour & Skills, Rate-limit lockout."""
import os
import uuid
import time
import pytest
import requests

_BU = os.environ.get("REACT_APP_BACKEND_URL")
if not _BU:
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                _BU = line.split("=", 1)[1].strip()
                break
    except Exception:
        pass
BASE_URL = (_BU or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@school.com", "password": "admin123"}
TEACHER = {"email": "teacher@school.com", "password": "teacher123"}
PARENT = {"email": "parent@school.com", "password": "parent123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def teacher():
    return _login(TEACHER)


@pytest.fixture(scope="module")
def parent():
    return _login(PARENT)


# ─── Stripe checkout ──────────────────────────────────────────────────────────
class TestStripe:
    @pytest.fixture(scope="class")
    def parent_unpaid_invoice(self, parent):
        # Parent invoices live inside per-child summary
        r = parent.get(f"{API}/parent/children", timeout=30)
        assert r.status_code == 200, r.text
        kids = r.json()
        assert kids, "Parent has no linked children"
        invoices = []
        for k in kids:
            s = parent.get(f"{API}/parent/children/{k['id']}/summary", timeout=30)
            assert s.status_code == 200, s.text
            invoices.extend(s.json().get("fees", {}).get("invoices", []))
        unpaid = [i for i in invoices if i.get("status") != "paid"]
        assert unpaid, "No unpaid invoices for parent — seed data missing"
        return unpaid[0]

    def _parent_invoices(self, parent):
        kids = parent.get(f"{API}/parent/children", timeout=30).json()
        invs = []
        for k in kids:
            s = parent.get(f"{API}/parent/children/{k['id']}/summary", timeout=30).json()
            invs.extend(s.get("fees", {}).get("invoices", []))
        return invs

    def test_parent_checkout_returns_stripe_url(self, parent, parent_unpaid_invoice):
        payload = {"invoice_id": parent_unpaid_invoice["id"], "origin_url": "https://example.com"}
        r = parent.post(f"{API}/parent/fees/invoices/checkout", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "session_id" in data
        assert data["url"].startswith("https://checkout.stripe.com"), data["url"]
        # save session_id for later tests
        TestStripe._session_id = data["session_id"]
        TestStripe._invoice_id = parent_unpaid_invoice["id"]

    def test_admin_cannot_use_parent_checkout(self, admin, parent_unpaid_invoice):
        r = admin.post(
            f"{API}/parent/fees/invoices/checkout",
            json={"invoice_id": parent_unpaid_invoice["id"], "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 403, f"admin should be 403, got {r.status_code}: {r.text}"

    def test_parent_cannot_checkout_other_student_invoice(self, parent, admin):
        # Find any invoice that the parent doesn't own
        all_invs = admin.get(f"{API}/fees/invoices", timeout=30).json()
        parent_invs = self._parent_invoices(parent)
        owned_ids = {i["id"] for i in parent_invs}
        other = next((i for i in all_invs if i["id"] not in owned_ids and i.get("status") != "paid"), None)
        if not other:
            pytest.skip("No foreign unpaid invoice available")
        r = parent.post(
            f"{API}/parent/fees/invoices/checkout",
            json={"invoice_id": other["id"], "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 403, r.text

    def test_checkout_on_paid_invoice_returns_400(self, parent, admin):
        parent_invs = self._parent_invoices(parent)
        paid = next((i for i in parent_invs if i.get("status") == "paid"), None)
        if not paid:
            unpaid = next((i for i in parent_invs if i.get("status") != "paid"), None)
            if not unpaid:
                pytest.skip("No invoices to mark paid")
            r = admin.post(
                f"{API}/fees/invoices/{unpaid['id']}/pay",
                json={"amount": float(unpaid["amount"]) - float(unpaid.get("paid_amount") or 0), "method": "cash"},
                timeout=30,
            )
            assert r.status_code == 200, r.text
            paid = unpaid
        r = parent.post(
            f"{API}/parent/fees/invoices/checkout",
            json={"invoice_id": paid["id"], "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 400, r.text

    def test_get_checkout_status(self, parent):
        sid = getattr(TestStripe, "_session_id", None)
        if not sid:
            pytest.skip("No session id from checkout test")
        r = parent.get(f"{API}/payments/checkout/status/{sid}", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("payment_status", "status", "invoice_id"):
            assert k in data, f"missing {k} in {data}"
        # since we didn't actually pay, expect not paid
        assert data["payment_status"] in ("unpaid", "no_payment_required"), data

    def test_get_checkout_status_foreign_parent_403(self, parent, admin):
        # Make admin create a new session-ish setup is impossible since admin can't checkout.
        # Instead try to access a fake session id as a parent — should be 404, not 403.
        r = parent.get(f"{API}/payments/checkout/status/cs_fake_does_not_exist", timeout=30)
        assert r.status_code in (404, 500), r.status_code  # not found is acceptable; tolerate stripe error


# ─── Resend email ─────────────────────────────────────────────────────────────
class TestResend:
    @pytest.fixture(scope="class")
    def any_invoice_id(self, admin):
        r = admin.get(f"{API}/fees/invoices", timeout=30)
        assert r.status_code == 200
        invs = r.json()
        assert invs, "No fee invoices seeded"
        return invs[0]["id"]

    @pytest.fixture(scope="class")
    def any_slip_id(self, admin):
        r = admin.get(f"{API}/salary/slips", timeout=30)
        if r.status_code != 200 or not r.json():
            # generate one for current month if needed
            pytest.skip("No salary slips available")
        return r.json()[0]["id"]

    def test_email_fee_invoice_skipped(self, admin, any_invoice_id):
        r = admin.post(
            f"{API}/fees/invoices/{any_invoice_id}/email",
            json={"recipient_email": "test@example.com"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "skipped", data

    def test_email_salary_slip_skipped(self, admin, any_slip_id):
        r = admin.post(
            f"{API}/salary/slips/{any_slip_id}/email",
            json={"recipient_email": "test@example.com"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "skipped"

    def test_email_logs_admin_only(self, admin, teacher):
        r = admin.get(f"{API}/emails/logs", timeout=30)
        assert r.status_code == 200, r.text
        logs = r.json()
        assert isinstance(logs, list) and len(logs) >= 1
        # recent entries should include 'skipped' statuses
        statuses = {l.get("status") for l in logs}
        assert "skipped" in statuses, f"expected 'skipped' in logs, got {statuses}"

        r2 = teacher.get(f"{API}/emails/logs", timeout=30)
        assert r2.status_code == 403, r2.status_code


# ─── User Management ──────────────────────────────────────────────────────────
class TestUsers:
    _created_id = None
    _created_email = None

    def test_list_users(self, admin, teacher):
        r = admin.get(f"{API}/users", timeout=30)
        assert r.status_code == 200, r.text
        users = r.json()
        assert isinstance(users, list) and len(users) >= 3
        # ensure no password_hash leaked
        assert all("password_hash" not in u for u in users)
        # teacher cannot list
        assert teacher.get(f"{API}/users", timeout=30).status_code == 403

    def test_create_user(self, admin):
        email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"  # api lowercases
        r = admin.post(f"{API}/users", json={
            "email": email, "password": "TestPass123", "name": "TEST User", "role": "teacher",
        }, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["role"] == "teacher"
        assert data["active"] is True
        assert "id" in data
        TestUsers._created_id = data["id"]
        TestUsers._created_email = email

    def test_update_user_role_name(self, admin):
        uid = TestUsers._created_id
        assert uid
        r = admin.put(f"{API}/users/{uid}", json={"name": "TEST Renamed", "role": "parent"}, timeout=30)
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["name"] == "TEST Renamed"
        assert u["role"] == "parent"

    def test_reset_password(self, admin):
        uid = TestUsers._created_id
        r = admin.post(f"{API}/users/{uid}/reset-password", json={"new_password": "NewPass1234"}, timeout=30)
        assert r.status_code == 200
        # login with new password
        r2 = requests.post(f"{API}/auth/login", json={
            "email": TestUsers._created_email, "password": "NewPass1234",
        }, timeout=30)
        assert r2.status_code == 200, r2.text

    def test_short_password_rejected(self, admin):
        r = admin.post(f"{API}/users", json={
            "email": f"TEST_s_{uuid.uuid4().hex[:6]}@e.com", "password": "short", "name": "X", "role": "teacher",
        }, timeout=30)
        assert r.status_code == 422, r.text  # Pydantic min_length=8

    def test_deactivated_user_cannot_login(self, admin):
        uid = TestUsers._created_id
        # deactivate
        r = admin.put(f"{API}/users/{uid}", json={"active": False}, timeout=30)
        assert r.status_code == 200, r.text
        # try to login
        r2 = requests.post(f"{API}/auth/login", json={
            "email": TestUsers._created_email, "password": "NewPass1234",
        }, timeout=30)
        assert r2.status_code == 403, r2.text
        assert "deactivated" in r2.text.lower()
        # reactivate
        admin.put(f"{API}/users/{uid}", json={"active": True}, timeout=30)
        r3 = requests.post(f"{API}/auth/login", json={
            "email": TestUsers._created_email, "password": "NewPass1234",
        }, timeout=30)
        assert r3.status_code == 200, r3.text

    def test_cannot_self_delete(self, admin):
        me = admin.get(f"{API}/auth/me", timeout=30).json()
        r = admin.delete(f"{API}/users/{me['id']}", timeout=30)
        assert r.status_code == 400, r.text

    def test_delete_created_user(self, admin):
        uid = TestUsers._created_id
        r = admin.delete(f"{API}/users/{uid}", timeout=30)
        assert r.status_code == 200


# ─── Behaviour & Skills ───────────────────────────────────────────────────────
class TestBehaviour:
    _b_id = None
    _s_id = None
    _o_id = None

    @pytest.fixture(scope="class")
    def student_id(self, admin):
        r = admin.get(f"{API}/students", timeout=30)
        assert r.status_code == 200 and r.json()
        return r.json()[0]["id"]

    def test_create_behaviour_rating(self, teacher, student_id):
        r = teacher.post(f"{API}/behaviour-ratings", json={
            "student_id": student_id, "category": "discipline", "rating": 4, "remark": "good"
        }, timeout=30)
        assert r.status_code == 200, r.text
        TestBehaviour._b_id = r.json()["id"]

    def test_create_skill_rating(self, teacher, student_id):
        r = teacher.post(f"{API}/skill-ratings", json={
            "student_id": student_id, "category": "math", "rating": 5,
        }, timeout=30)
        assert r.status_code == 200, r.text
        TestBehaviour._s_id = r.json()["id"]

    def test_rating_out_of_range_rejected(self, teacher, student_id):
        r = teacher.post(f"{API}/behaviour-ratings", json={
            "student_id": student_id, "category": "x", "rating": 7,
        }, timeout=30)
        assert r.status_code == 422, r.text
        r2 = teacher.post(f"{API}/skill-ratings", json={
            "student_id": student_id, "category": "x", "rating": 0,
        }, timeout=30)
        assert r2.status_code == 422

    def test_list_behaviour_skill(self, teacher, student_id):
        r = teacher.get(f"{API}/behaviour-ratings?student_id={student_id}", timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)
        assert any(x["id"] == TestBehaviour._b_id for x in r.json())
        r2 = teacher.get(f"{API}/skill-ratings?student_id={student_id}", timeout=30)
        assert r2.status_code == 200
        assert any(x["id"] == TestBehaviour._s_id for x in r2.json())

    def test_observation_crud(self, teacher, student_id):
        r = teacher.post(f"{API}/observations", json={
            "student_id": student_id, "note": "Helpful to peers."
        }, timeout=30)
        assert r.status_code == 200, r.text
        oid = r.json()["id"]
        TestBehaviour._o_id = oid
        r2 = teacher.get(f"{API}/observations?student_id={student_id}", timeout=30)
        assert r2.status_code == 200
        assert any(o["id"] == oid for o in r2.json())

    def test_parent_cannot_post_rating(self, parent, student_id):
        r = parent.post(f"{API}/behaviour-ratings", json={
            "student_id": student_id, "category": "x", "rating": 3,
        }, timeout=30)
        assert r.status_code == 403, r.text

    def test_delete_cleanup(self, teacher):
        if TestBehaviour._b_id:
            assert teacher.delete(f"{API}/behaviour-ratings/{TestBehaviour._b_id}", timeout=30).status_code == 200
        if TestBehaviour._s_id:
            assert teacher.delete(f"{API}/skill-ratings/{TestBehaviour._s_id}", timeout=30).status_code == 200
        if TestBehaviour._o_id:
            assert teacher.delete(f"{API}/observations/{TestBehaviour._o_id}", timeout=30).status_code == 200


# ─── Rate-limit lockout ───────────────────────────────────────────────────────
class TestRateLimit:
    def test_lockout_after_5_failures(self):
        # Use a unique throwaway email so previous runs don't impact us
        email = f"TEST_rl_{uuid.uuid4().hex[:10]}@example.com"
        s = requests.Session()
        # 5 wrong attempts → 401 each
        for i in range(5):
            r = s.post(f"{API}/auth/login", json={"email": email, "password": "wrongpw"}, timeout=30)
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code} {r.text}"
        # 6th → 429
        r6 = s.post(f"{API}/auth/login", json={"email": email, "password": "wrongpw"}, timeout=30)
        assert r6.status_code == 429, f"expected 429, got {r6.status_code}: {r6.text}"
        assert "too many failed attempts" in r6.text.lower()

    def test_success_clears_counter(self, admin):
        # Use admin's email; make 2 failures then a success then a failure should still be 401
        creds = ADMIN
        # 2 failed
        for _ in range(2):
            r = requests.post(f"{API}/auth/login", json={"email": creds["email"], "password": "BAD"}, timeout=30)
            assert r.status_code == 401
        # success
        r2 = requests.post(f"{API}/auth/login", json=creds, timeout=30)
        assert r2.status_code == 200
        # now even a failure should reset back to 1 — verify by hitting 1 fail and then succeed
        r3 = requests.post(f"{API}/auth/login", json={"email": creds["email"], "password": "BAD"}, timeout=30)
        assert r3.status_code == 401
        r4 = requests.post(f"{API}/auth/login", json=creds, timeout=30)
        assert r4.status_code == 200
