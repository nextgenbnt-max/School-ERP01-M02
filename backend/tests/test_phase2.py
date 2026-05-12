"""Phase 2 backend regression: Salary, Accounts, Homework, Promote, PDF exports."""
import os
import pytest
import requests
from datetime import date

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://edumanage-core-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@school.com", "password": "admin123"}
TEACHER = {"email": "teacher@school.com", "password": "teacher123"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def teacher():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=TEACHER, timeout=30)
    assert r.status_code == 200
    return s


# ─── Salary ───────────────────────────────────────────────────────────────────
class TestSalary:
    def test_list_slips_attaches_employee(self, admin):
        r = admin.get(f"{API}/salary/slips", timeout=30)
        assert r.status_code == 200
        slips = r.json()
        assert isinstance(slips, list) and len(slips) >= 1
        first = slips[0]
        for k in ("id", "employee_id", "month", "year", "net_amount", "status",
                  "employee_name", "employee_role"):
            assert k in first, f"missing {k}"

    def test_list_slips_filters(self, admin):
        r = admin.get(f"{API}/salary/slips?status=pending", timeout=30)
        assert r.status_code == 200
        for s in r.json():
            assert s["status"] == "pending"

    def test_bulk_generate_idempotent(self, admin):
        month, year = 7, 2099
        r1 = admin.post(f"{API}/salary/slips/bulk-generate?month={month}&year={year}", timeout=30)
        assert r1.status_code == 200
        created1 = r1.json()["created"]
        r2 = admin.post(f"{API}/salary/slips/bulk-generate?month={month}&year={year}", timeout=30)
        assert r2.status_code == 200
        assert r2.json()["created"] == 0  # idempotent
        assert created1 >= 1

    def test_pay_creates_expense_txn(self, admin):
        # find a pending slip
        slips = admin.get(f"{API}/salary/slips?status=pending", timeout=30).json()
        if not slips:
            # create one
            slips = admin.get(f"{API}/salary/slips", timeout=30).json()
        slip = next((s for s in slips if s["status"] == "pending"), None)
        assert slip is not None, "no pending slip"
        # baseline txn count on EXP-SAL
        accts = admin.get(f"{API}/accounts", timeout=30).json()
        sal = next(a for a in accts if a["code"] == "EXP-SAL")
        before = admin.get(f"{API}/transactions?account_id={sal['id']}", timeout=30).json()
        n_before = len(before)
        # pay
        r = admin.post(f"{API}/salary/slips/{slip['id']}/pay",
                       json={"payment_method": "bank", "notes": "TEST"}, timeout=30)
        assert r.status_code == 200
        paid = r.json()
        assert paid["status"] == "paid"
        assert paid["paid_date"] is not None
        assert paid["payment_method"] == "bank"
        # txn auto-created
        after = admin.get(f"{API}/transactions?account_id={sal['id']}", timeout=30).json()
        assert len(after) == n_before + 1
        new_txn = next(t for t in after if t.get("reference") == slip["id"])
        assert new_txn["type"] == "expense"
        assert new_txn["amount"] == slip["net_amount"]

    def test_salary_report(self, admin):
        r = admin.get(f"{API}/salary/report", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_payroll", "total_paid", "total_pending", "by_month"):
            assert k in d
        assert isinstance(d["by_month"], list)
        assert d["total_payroll"] >= d["total_paid"]

    def test_teacher_cannot_create_slip(self, teacher):
        r = teacher.post(f"{API}/salary/slips", json={
            "employee_id": "fake", "month": 1, "year": 2099,
            "base_salary": 1000, "bonus": 0, "deductions": 0,
        }, timeout=30)
        assert r.status_code == 403


# ─── Accounts ─────────────────────────────────────────────────────────────────
class TestAccounts:
    def test_seeded_chart(self, admin):
        r = admin.get(f"{API}/accounts", timeout=30)
        assert r.status_code == 200
        accts = r.json()
        codes = {a["code"] for a in accts}
        for c in ("INC-FEE", "INC-MISC", "EXP-SAL", "EXP-UTIL", "EXP-SUPPLY",
                  "EXP-MAINT", "ASSET-CASH", "ASSET-BANK"):
            assert c in codes, f"missing {c}"

    def test_create_account_unique_and_validation(self, admin):
        code = "TEST-ACCT-001"
        # cleanup if leftover
        for a in admin.get(f"{API}/accounts").json():
            if a["code"] == code:
                admin.delete(f"{API}/accounts/{a['id']}")
        r = admin.post(f"{API}/accounts", json={
            "name": "TEST Account", "code": code, "type": "income",
        }, timeout=30)
        assert r.status_code == 200
        acct = r.json()
        assert acct["code"] == code
        # duplicate
        r2 = admin.post(f"{API}/accounts", json={
            "name": "dup", "code": code, "type": "income",
        }, timeout=30)
        assert r2.status_code == 400
        # invalid type
        r3 = admin.post(f"{API}/accounts", json={
            "name": "bad", "code": "TEST-BAD-001", "type": "bogus",
        }, timeout=30)
        assert r3.status_code == 400
        # update
        rput = admin.put(f"{API}/accounts/{acct['id']}", json={
            "name": "TEST Account Renamed", "code": code, "type": "income",
        }, timeout=30)
        assert rput.status_code == 200
        assert rput.json()["name"] == "TEST Account Renamed"
        # delete (no txn) succeeds
        rdel = admin.delete(f"{API}/accounts/{acct['id']}", timeout=30)
        assert rdel.status_code == 200

    def test_delete_account_with_txn_fails(self, admin):
        accts = admin.get(f"{API}/accounts", timeout=30).json()
        sal = next(a for a in accts if a["code"] == "EXP-SAL")
        # ensure txn exists by creating one if needed
        txns = admin.get(f"{API}/transactions?account_id={sal['id']}", timeout=30).json()
        if not txns:
            admin.post(f"{API}/transactions", json={
                "account_id": sal["id"], "type": "expense", "amount": 1.0,
                "date": date.today().isoformat(), "description": "TEST",
            }, timeout=30)
        r = admin.delete(f"{API}/accounts/{sal['id']}", timeout=30)
        assert r.status_code == 400


# ─── Transactions ─────────────────────────────────────────────────────────────
class TestTransactions:
    def test_list_attaches_account(self, admin):
        items = admin.get(f"{API}/transactions", timeout=30).json()
        assert isinstance(items, list)
        if items:
            assert "account_name" in items[0]
            assert "account_code" in items[0]

    def test_create_and_filter(self, admin):
        accts = admin.get(f"{API}/accounts", timeout=30).json()
        cash = next(a for a in accts if a["code"] == "ASSET-CASH")
        # create income txn
        r = admin.post(f"{API}/transactions", json={
            "account_id": cash["id"], "type": "income", "amount": 250.0,
            "date": "2099-03-15", "description": "TEST income",
        }, timeout=30)
        assert r.status_code == 200
        txn = r.json()
        # filter by type
        inc = admin.get(f"{API}/transactions?type=income&account_id={cash['id']}", timeout=30).json()
        assert any(t["id"] == txn["id"] for t in inc)
        # date range
        rng = admin.get(f"{API}/transactions?start=2099-03-01&end=2099-03-31", timeout=30).json()
        assert any(t["id"] == txn["id"] for t in rng)
        # delete
        rdel = admin.delete(f"{API}/transactions/{txn['id']}", timeout=30)
        assert rdel.status_code == 200

    def test_create_invalid(self, admin):
        r = admin.post(f"{API}/transactions", json={
            "account_id": "nonexistent", "type": "income", "amount": 1,
            "date": "2099-01-01",
        }, timeout=30)
        assert r.status_code == 400
        accts = admin.get(f"{API}/accounts").json()
        a0 = accts[0]
        r2 = admin.post(f"{API}/transactions", json={
            "account_id": a0["id"], "type": "bogus", "amount": 1,
            "date": "2099-01-01",
        }, timeout=30)
        assert r2.status_code == 400

    def test_account_statement(self, admin):
        r = admin.get(f"{API}/accounts/statement", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_income", "total_expense", "net", "transactions"):
            assert k in d
        if d["transactions"]:
            assert "running_balance" in d["transactions"][0]


# ─── Homework ─────────────────────────────────────────────────────────────────
class TestHomework:
    def test_list_with_chips(self, admin):
        r = admin.get(f"{API}/homework", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            assert "class_name" in items[0]

    def test_class_filter(self, admin):
        classes = admin.get(f"{API}/classes", timeout=30).json()
        if not classes:
            pytest.skip("no classes")
        cid = classes[0]["id"]
        r = admin.get(f"{API}/homework?class_id={cid}", timeout=30).json()
        for h in r:
            assert h["class_id"] == cid

    def test_active_filter(self, admin):
        r = admin.get(f"{API}/homework?active=true", timeout=30)
        assert r.status_code == 200
        today = date.today().isoformat()
        for h in r.json():
            assert h["due_date"] >= today

    def test_teacher_can_crud(self, teacher, admin):
        classes = admin.get(f"{API}/classes").json()
        subjects = admin.get(f"{API}/subjects").json()
        if not classes:
            pytest.skip("no classes")
        payload = {
            "class_id": classes[0]["id"],
            "subject_id": subjects[0]["id"] if subjects else None,
            "title": "TEST homework",
            "description": "desc",
            "assigned_date": date.today().isoformat(),
            "due_date": "2099-12-31",
        }
        r = teacher.post(f"{API}/homework", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        hw = r.json()
        # update
        upd = dict(payload, title="TEST homework updated")
        rput = teacher.put(f"{API}/homework/{hw['id']}", json=upd, timeout=30)
        assert rput.status_code == 200
        assert rput.json()["title"] == "TEST homework updated"
        # delete
        rdel = teacher.delete(f"{API}/homework/{hw['id']}", timeout=30)
        assert rdel.status_code == 200


# ─── Promote ──────────────────────────────────────────────────────────────────
class TestPromote:
    def test_invalid_to_class(self, admin):
        classes = admin.get(f"{API}/classes").json()
        if not classes:
            pytest.skip("no classes")
        r = admin.post(f"{API}/students/promote", json={
            "from_class_id": classes[0]["id"],
            "to_class_id": "nonexistent-xxx",
        }, timeout=30)
        assert r.status_code == 400

    def test_promote_moves_students(self, admin):
        classes = admin.get(f"{API}/classes").json()
        if len(classes) < 2:
            pytest.skip("need >=2 classes")
        # find a class with students
        from_c, to_c = None, None
        for c in classes:
            studs = admin.get(f"{API}/students?class_id={c['id']}").json()
            if studs:
                from_c = c
                to_c = next((x for x in classes if x["id"] != c["id"]), None)
                break
        if not from_c or not to_c:
            pytest.skip("no class with students")
        before = admin.get(f"{API}/students?class_id={from_c['id']}").json()
        ids = [s["id"] for s in before[:1]]  # just promote one to be safe
        r = admin.post(f"{API}/students/promote", json={
            "from_class_id": from_c["id"], "to_class_id": to_c["id"],
            "student_ids": ids,
        }, timeout=30)
        assert r.status_code == 200
        # verify
        moved = admin.get(f"{API}/students/{ids[0]}").json()
        assert moved["class_id"] == to_c["id"]
        # move back to keep state clean
        admin.post(f"{API}/students/promote", json={
            "from_class_id": to_c["id"], "to_class_id": from_c["id"],
            "student_ids": ids,
        }, timeout=30)


# ─── PDF Exports ──────────────────────────────────────────────────────────────
class TestPDF:
    def test_fee_slip_pdf(self, admin):
        invs = admin.get(f"{API}/fees/invoices", timeout=30).json()
        if not invs:
            pytest.skip("no invoices")
        r = admin.get(f"{API}/fees/invoices/{invs[0]['id']}/slip.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_salary_slip_pdf(self, admin):
        slips = admin.get(f"{API}/salary/slips", timeout=30).json()
        if not slips:
            pytest.skip("no slips")
        r = admin.get(f"{API}/salary/slips/{slips[0]['id']}/slip.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_admission_letter_pdf(self, admin):
        studs = admin.get(f"{API}/students", timeout=30).json()
        if not studs:
            pytest.skip("no students")
        r = admin.get(f"{API}/students/{studs[0]['id']}/admission-letter.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
