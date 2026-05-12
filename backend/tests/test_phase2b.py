"""Phase 2B backend regression: Timetable, Exams, Question Papers, ID-cards/Certs/Letters PDFs, Parent Portal."""
import os
import uuid
import pytest
import requests

_BU = os.environ.get("REACT_APP_BACKEND_URL")
if not _BU:
    # fallback to frontend/.env value used by the live app
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


# ─── Timetable ────────────────────────────────────────────────────────────────
class TestTimetable:
    def test_get_config_seeded(self, admin):
        r = admin.get(f"{API}/timetable/config", timeout=30)
        assert r.status_code == 200
        c = r.json()
        for k in ("weekdays", "periods", "classrooms"):
            assert k in c
        assert isinstance(c["weekdays"], list) and len(c["weekdays"]) >= 5
        assert isinstance(c["periods"], list) and len(c["periods"]) >= 1

    def test_update_config_admin_only(self, admin, teacher):
        # capture current
        cur = admin.get(f"{API}/timetable/config", timeout=30).json()
        payload = {
            "weekdays": cur["weekdays"],
            "periods": cur["periods"],
            "classrooms": cur.get("classrooms", []) + ["TEST-ROOM-Z"],
        }
        r_t = teacher.put(f"{API}/timetable/config", json=payload, timeout=30)
        assert r_t.status_code == 403
        r = admin.put(f"{API}/timetable/config", json=payload, timeout=30)
        assert r.status_code == 200
        # verify persisted
        again = admin.get(f"{API}/timetable/config", timeout=30).json()
        assert "TEST-ROOM-Z" in again["classrooms"]
        # revert
        admin.put(f"{API}/timetable/config", json={
            "weekdays": cur["weekdays"], "periods": cur["periods"],
            "classrooms": cur.get("classrooms", []),
        }, timeout=30)

    def test_get_timetable_returns_slots_with_names(self, admin):
        classes = admin.get(f"{API}/classes", timeout=30).json()
        assert classes, "no classes seeded"
        cid = classes[0]["id"]
        r = admin.get(f"{API}/timetable?class_id={cid}", timeout=30)
        assert r.status_code == 200
        slots = r.json()
        assert isinstance(slots, list) and len(slots) >= 1
        s = slots[0]
        for k in ("id", "class_id", "weekday", "period_index", "subject_id", "teacher_id"):
            assert k in s
        # display-name attachments
        assert "subject_name" in s or "subject" in s
        assert "teacher_name" in s or "teacher" in s
        assert "class_name" in s or "class" in s

    def test_slot_upsert_idempotent(self, admin):
        classes = admin.get(f"{API}/classes", timeout=30).json()
        subjects = admin.get(f"{API}/subjects", timeout=30).json()
        teachers = admin.get(f"{API}/employees?role=teacher", timeout=30).json()
        if not teachers:
            teachers = admin.get(f"{API}/employees", timeout=30).json()
        assert classes and subjects and teachers
        cid = classes[0]["id"]
        # pick a likely-unused weekday/period combo
        payload = {
            "class_id": cid,
            "weekday": "Saturday",
            "period_index": 99,
            "subject_id": subjects[0]["id"],
            "teacher_id": teachers[0]["id"],
            "room": "TEST-ROOM",
        }
        # API field is `classroom`, accept either
        payload["classroom"] = payload.pop("room")
        r1 = admin.post(f"{API}/timetable/slot", json=payload, timeout=30)
        assert r1.status_code == 200, r1.text
        slot1 = r1.json()
        # repost same combo with different classroom → should UPDATE not duplicate
        payload2 = dict(payload, classroom="TEST-ROOM-UPDATED")
        r2 = admin.post(f"{API}/timetable/slot", json=payload2, timeout=30)
        assert r2.status_code == 200
        slot2 = r2.json()
        assert slot2["id"] == slot1["id"], "slot upsert created duplicate"
        assert slot2.get("classroom") == "TEST-ROOM-UPDATED"
        # cleanup
        d = admin.delete(f"{API}/timetable/slot/{slot1['id']}", timeout=30)
        assert d.status_code == 200


# ─── Exams ────────────────────────────────────────────────────────────────────
class TestExams:
    def test_list_exams_with_meta(self, admin):
        r = admin.get(f"{API}/exams", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        first = items[0]
        assert "class_name" in first
        assert "subject_count" in first
        assert isinstance(first["subject_count"], int)

    def test_create_exam_subjects_results_marksheet_and_delete_cascades(self, admin):
        classes = admin.get(f"{API}/classes", timeout=30).json()
        subjects = admin.get(f"{API}/subjects", timeout=30).json()
        cid = classes[0]["id"]
        students = admin.get(f"{API}/students?class_id={cid}", timeout=30).json()
        assert students, "no students in first class"
        sid = students[0]["id"]
        # create exam (server requires start_date/end_date)
        exam_payload = {
            "name": f"TEST-EXAM-{uuid.uuid4().hex[:6]}",
            "class_id": cid,
            "start_date": "2099-05-10",
            "end_date": "2099-05-20",
        }
        r = admin.post(f"{API}/exams", json=exam_payload, timeout=30)
        assert r.status_code == 200, r.text
        exam = r.json()
        eid = exam["id"]
        # add 2 subjects (ExamSubjectIn requires exam_date)
        es_ids = []
        for i, sub in enumerate(subjects[:2]):
            rs = admin.post(f"{API}/exams/{eid}/subjects", json={
                "subject_id": sub["id"],
                "exam_date": f"2099-05-{10+i:02d}",
                "max_marks": 100,
                "pass_marks": 35,
            }, timeout=30)
            assert rs.status_code == 200, rs.text
            es_ids.append(rs.json()["id"])
        # list subjects
        sl = admin.get(f"{API}/exams/{eid}/subjects", timeout=30).json()
        assert len(sl) >= 2
        # upsert marks
        results_payload = [
            {"student_id": sid, "subject_id": subjects[0]["id"], "marks": 80},
            {"student_id": sid, "subject_id": subjects[1]["id"], "marks": 70},
        ]
        rr = admin.post(f"{API}/exams/{eid}/results", json=results_payload, timeout=30)
        assert rr.status_code == 200, rr.text
        # re-upsert (replaces) — change a mark, ensure no duplicate
        results_payload[0]["marks"] = 90
        rr2 = admin.post(f"{API}/exams/{eid}/results", json=results_payload, timeout=30)
        assert rr2.status_code == 200
        all_r = admin.get(f"{API}/exams/{eid}/results?student_id={sid}", timeout=30).json()
        marks_for_sub0 = [x for x in all_r if x["subject_id"] == subjects[0]["id"]]
        assert len(marks_for_sub0) == 1, "results not upserted, duplicate found"
        assert marks_for_sub0[0]["marks"] == 90
        # marksheet
        ms = admin.get(f"{API}/exams/{eid}/marksheet?student_id={sid}", timeout=30)
        assert ms.status_code == 200, ms.text
        sheet = ms.json()
        for k in ("student", "rows", "total_marks", "total_max", "percentage", "overall_grade"):
            assert k in sheet, f"marksheet missing {k}"
        assert sheet["total_max"] >= 200
        assert sheet["total_marks"] == 90 + 70
        assert abs(sheet["percentage"] - 80.0) < 0.5
        assert isinstance(sheet["overall_grade"], str) and sheet["overall_grade"]
        assert len(sheet["rows"]) >= 2
        assert "grade" in sheet["rows"][0]
        # DELETE exam → cascades
        rd = admin.delete(f"{API}/exams/{eid}", timeout=30)
        assert rd.status_code == 200
        # subjects gone
        sl2 = admin.get(f"{API}/exams/{eid}/subjects", timeout=30).json()
        assert sl2 == []
        rs2 = admin.get(f"{API}/exams/{eid}/results", timeout=30).json()
        assert rs2 == []

    def test_teacher_can_create_exam(self, teacher):
        classes = teacher.get(f"{API}/classes", timeout=30).json()
        r = teacher.post(f"{API}/exams", json={
            "name": f"TEST-T-{uuid.uuid4().hex[:6]}",
            "class_id": classes[0]["id"],
            "start_date": "2099-06-01",
            "end_date": "2099-06-05",
        }, timeout=30)
        assert r.status_code == 200
        eid = r.json()["id"]
        # cleanup via admin (teachers can't delete in spec) — try teacher first
        rd = teacher.delete(f"{API}/exams/{eid}", timeout=30)
        # delete is admin-only per server (line 1334), accept 403 silently
        assert rd.status_code in (200, 403)


# ─── Question Papers ──────────────────────────────────────────────────────────
class TestQuestionPapers:
    def test_list_seeded(self, admin):
        r = admin.get(f"{API}/question-papers", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1

    def test_crud_and_pdf(self, admin):
        classes = admin.get(f"{API}/classes", timeout=30).json()
        subjects = admin.get(f"{API}/subjects", timeout=30).json()
        payload = {
            "title": f"TEST-QP-{uuid.uuid4().hex[:6]}",
            "class_id": classes[0]["id"],
            "subject_id": subjects[0]["id"],
            "exam_type": "Unit Test",
            "duration_minutes": 60,
            "total_marks": 25,
            "questions": [
                {"q": "What is 1+1?", "marks": 5},
                {"q": "Define velocity.", "marks": 10},
                {"q": "Explain photosynthesis.", "marks": 10},
            ],
        }
        r = admin.post(f"{API}/question-papers", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        qp = r.json()
        qid = qp["id"]
        # update
        upd = dict(payload, title=payload["title"] + "-UPD")
        ru = admin.put(f"{API}/question-papers/{qid}", json=upd, timeout=30)
        assert ru.status_code == 200
        # pdf
        rp = admin.get(f"{API}/question-papers/{qid}/pdf", timeout=60)
        assert rp.status_code == 200
        assert rp.headers.get("content-type", "").startswith("application/pdf")
        assert rp.content[:4] == b"%PDF"
        # delete
        rd = admin.delete(f"{API}/question-papers/{qid}", timeout=30)
        assert rd.status_code == 200


# ─── Student/Employee PDF docs ────────────────────────────────────────────────
class TestDocsPDF:
    def test_student_id_card(self, admin):
        studs = admin.get(f"{API}/students", timeout=30).json()
        sid = studs[0]["id"]
        r = admin.get(f"{API}/students/{sid}/id-card.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    @pytest.mark.parametrize("ctype", ["admission", "character", "transfer", "completion"])
    def test_student_certificate(self, admin, ctype):
        studs = admin.get(f"{API}/students", timeout=30).json()
        sid = studs[0]["id"]
        r = admin.get(f"{API}/students/{sid}/certificate.pdf?type={ctype}", timeout=60)
        assert r.status_code == 200, f"cert type={ctype}: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_employee_id_card(self, admin):
        emps = admin.get(f"{API}/employees", timeout=30).json()
        eid = emps[0]["id"]
        r = admin.get(f"{API}/employees/{eid}/id-card.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_employee_job_letter(self, admin):
        emps = admin.get(f"{API}/employees", timeout=30).json()
        eid = emps[0]["id"]
        r = admin.get(f"{API}/employees/{eid}/job-letter.pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# ─── Parent Portal ────────────────────────────────────────────────────────────
class TestParent:
    def test_self_register_parent_only(self):
        s = requests.Session()
        # non-parent role rejected
        r1 = s.post(f"{API}/auth/register", json={
            "email": f"TEST_admin_{uuid.uuid4().hex[:6]}@x.com",
            "password": "x123456", "name": "T", "role": "admin",
        }, timeout=30)
        assert r1.status_code == 403
        # parent role succeeds
        email = f"TEST_parent_{uuid.uuid4().hex[:6]}@x.com"
        r2 = s.post(f"{API}/auth/register", json={
            "email": email, "password": "x123456", "name": "TestP", "role": "parent",
        }, timeout=30)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["user"]["email"] == email.lower()
        assert body["user"]["role"] == "parent"

    def test_admin_blocked_from_parent_endpoints(self, admin):
        r = admin.get(f"{API}/parent/children", timeout=30)
        assert r.status_code == 403

    def test_seeded_demo_parent_has_2_children(self, parent):
        r = parent.get(f"{API}/parent/children", timeout=30)
        assert r.status_code == 200, r.text
        kids = r.json()
        assert isinstance(kids, list)
        assert len(kids) >= 2, f"demo parent expected >=2 linked kids, got {len(kids)}"

    def test_link_child_bad_reg(self, parent):
        r = parent.post(f"{API}/parent/link-child", json={
            "registration_number": "NO-SUCH-REG-12345",
        }, timeout=30)
        assert r.status_code == 404

    def test_link_unlink_child_roundtrip(self, admin, parent):
        # find a student NOT currently linked
        kids = parent.get(f"{API}/parent/children", timeout=30).json()
        linked_ids = {k["id"] for k in kids}
        studs = admin.get(f"{API}/students", timeout=30).json()
        target = next((s for s in studs if s["id"] not in linked_ids and s.get("registration_number")), None)
        if not target:
            pytest.skip("no spare student to link")
        reg = target["registration_number"]
        r1 = parent.post(f"{API}/parent/link-child", json={"registration_number": reg}, timeout=30)
        assert r1.status_code == 200, r1.text
        kids2 = parent.get(f"{API}/parent/children").json()
        assert any(k["id"] == target["id"] for k in kids2)
        # unlink
        r2 = parent.post(f"{API}/parent/unlink-child", json={"registration_number": reg}, timeout=30)
        assert r2.status_code == 200
        kids3 = parent.get(f"{API}/parent/children").json()
        assert not any(k["id"] == target["id"] for k in kids3)

    def test_child_summary_returns_data(self, parent):
        kids = parent.get(f"{API}/parent/children", timeout=30).json()
        assert kids, "no linked kids — cannot test summary"
        sid = kids[0]["id"]
        r = parent.get(f"{API}/parent/children/{sid}/summary", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # required keys
        keys = set(d.keys())
        assert "attendance" in keys or "attendance_counts" in keys
        assert "fees" in keys or "invoices" in keys
        assert "upcoming_homework" in keys or "homework" in keys

    def test_child_summary_403_if_unlinked(self, parent, admin):
        studs = admin.get(f"{API}/students", timeout=30).json()
        kids = parent.get(f"{API}/parent/children").json()
        linked_ids = {k["id"] for k in kids}
        spare = next((s for s in studs if s["id"] not in linked_ids), None)
        if not spare:
            pytest.skip("no unlinked student available")
        r = parent.get(f"{API}/parent/children/{spare['id']}/summary", timeout=30)
        assert r.status_code == 403
