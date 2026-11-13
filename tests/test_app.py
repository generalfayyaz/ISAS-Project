from datetime import date, timedelta
from io import BytesIO
import sqlite3

import pytest
from openpyxl import load_workbook

from app import create_app
from db import get_db


@pytest.fixture()
def app(tmp_path):
    database = tmp_path / "test.sqlite3"
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "DATABASE": str(database),
        "SEED_DATA": True,
    })
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


def test_seeded_records_and_login(client, app):
    response = login(client, "employee1", "Employee@123")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 8
        assert db.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 60
        counts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) n FROM claims GROUP BY status")}
        assert counts == {"Approved": 15, "Draft": 15, "Paid": 12, "Rejected": 8, "Submitted": 10}


def test_all_seeded_demo_accounts_can_log_in_and_out(client):
    accounts = [
        ("admin", "Admin@123"),
        ("finance1", "Finance@123"),
        ("finance2", "Finance@123"),
        ("manager_it", "Manager@123"),
        ("manager_marketing", "Manager@123"),
        ("employee1", "Employee@123"),
        ("employee2", "Employee@123"),
        ("employee3", "Employee@123"),
    ]
    for username, password in accounts:
        response = login(client, username, password)
        assert response.status_code == 200
        assert b"Dashboard" in response.data
        assert logout(client).status_code == 200


def test_employee_cannot_open_another_employees_claim(client, app):
    login(client, "employee1", "Employee@123")
    with app.app_context():
        other_claim = get_db().execute(
            "SELECT c.id FROM claims c JOIN users u ON u.id=c.employee_id WHERE u.username='employee2' LIMIT 1"
        ).fetchone()[0]
    response = client.get(f"/claims/{other_claim}")
    assert response.status_code == 403


def test_role_restricted_routes_are_enforced_on_the_server(client):
    checks = [
        ("employee1", "Employee@123", {
            "/admin/audit-log": 403,
            "/finance/payments": 403,
            "/approvals": 403,
        }),
        ("manager_it", "Manager@123", {
            "/admin/users": 403,
            "/finance/payments": 403,
        }),
        ("finance1", "Finance@123", {
            "/admin/audit-log": 403,
            "/approvals": 403,
        }),
        ("admin", "Admin@123", {
            "/finance/payments": 403,
            "/admin/audit-log": 200,
        }),
    ]
    for username, password, routes in checks:
        login(client, username, password)
        for path, expected_status in routes.items():
            assert client.get(path).status_code == expected_status
        logout(client)


def test_admin_can_create_and_edit_employee_account(client, app):
    login(client, "admin", "Admin@123")
    response = client.post("/admin/users/new", data={
        "username": "demo_employee",
        "full_name": "Demo Employee",
        "email": "demo.employee@example.test",
        "role": "Employee",
        "department": "Information Technology",
        "password": "Employee@456",
    })
    assert response.status_code == 302
    with app.app_context():
        user_id = get_db().execute(
            "SELECT id FROM users WHERE username='demo_employee'"
        ).fetchone()[0]

    response = client.post(f"/admin/users/{user_id}/edit", data={
        "full_name": "Updated Demo Employee",
        "email": "updated.demo.employee@example.test",
        "role": "Employee",
        "department": "Marketing",
        "password": "",
        "is_active": "1",
    })
    assert response.status_code == 302
    with app.app_context():
        user = get_db().execute(
            "SELECT full_name, email, department FROM users WHERE id=?", (user_id,)
        ).fetchone()
        assert tuple(user) == (
            "Updated Demo Employee", "updated.demo.employee@example.test", "Marketing"
        )
    logout(client)
    assert login(client, "demo_employee", "Employee@456").status_code == 200


def test_end_to_end_claim_submit_approve_and_pay(client, app):
    login(client, "employee1", "Employee@123")
    payload = {
        "category": "Travel",
        "amount": "450000",
        "expense_date": (date.today() - timedelta(days=2)).isoformat(),
        "receipt_number": "TST20261101",
        "description": "Travel cost for a project coordination meeting",
    }
    response = client.post("/claims/new", data=payload, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        claim = get_db().execute("SELECT * FROM claims WHERE receipt_number='TST20261101'").fetchone()
        claim_id = claim["id"]
        assert claim["status"] == "Draft"
    payload["description"] = "Updated travel cost for a project coordination meeting"
    response = client.post(f"/claims/{claim_id}/edit", data=payload, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        claim = get_db().execute("SELECT status, description FROM claims WHERE id=?", (claim_id,)).fetchone()
        assert claim["status"] == "Draft"
        assert claim["description"] == payload["description"]
    assert b"EXP-" in client.get(f"/claims/{claim_id}").data
    response = client.post(f"/claims/{claim_id}/submit", follow_redirects=False)
    assert response.status_code == 302
    logout(client)

    login(client, "manager_it", "Manager@123")
    assert b"Department approval inbox" in client.get("/approvals").data
    response = client.post(f"/approvals/{claim_id}/decision", data={
        "decision": "Approved", "comment": "Receipt checked and expense is within policy."
    }, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT status FROM claims WHERE id=?", (claim_id,)).fetchone()[0] == "Approved"
    logout(client)

    login(client, "finance1", "Finance@123")
    response = client.post(f"/finance/payments/{claim_id}/pay", data={
        "payment_date": date.today().isoformat(), "payment_reference": "PAY-TST-001"
    }, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        paid = get_db().execute("SELECT status, payment_reference FROM claims WHERE id=?", (claim_id,)).fetchone()
        assert paid["status"] == "Paid"
        assert paid["payment_reference"] == "PAY-TST-001"
    assert client.post(f"/finance/payments/{claim_id}/pay", data={
        "payment_date": date.today().isoformat(), "payment_reference": "PAY-TST-002"
    }).status_code == 403
    logout(client)

    login(client, "admin", "Admin@123")
    audit = client.get("/admin/audit-log")
    assert audit.status_code == 200
    assert b"PAY" in audit.data
    assert str(claim_id).encode() in audit.data
    with app.app_context():
        actions = {r["action"] for r in get_db().execute(
            "SELECT action FROM audit_log WHERE record_id=?", (claim_id,)
        )}
        assert {"CREATE", "UPDATE", "SUBMIT", "APPROVE", "PAY"} <= actions


def test_manager_can_reject_and_employee_can_edit_and_resubmit(client, app):
    login(client, "employee1", "Employee@123")
    response = client.post("/claims/new", data={
        "category": "Meals",
        "amount": "125000",
        "expense_date": (date.today() - timedelta(days=1)).isoformat(),
        "receipt_number": "REJECT001",
        "description": "Meal expense for a project planning session",
    })
    assert response.status_code == 302
    with app.app_context():
        claim_id = get_db().execute(
            "SELECT id FROM claims WHERE receipt_number='REJECT001'"
        ).fetchone()[0]
    client.post(f"/claims/{claim_id}/submit")
    logout(client)

    login(client, "manager_it", "Manager@123")
    response = client.post(f"/approvals/{claim_id}/decision", data={
        "decision": "Rejected",
        "comment": "Please provide a clearer business purpose for this expense.",
    })
    assert response.status_code == 302
    logout(client)

    login(client, "employee1", "Employee@123")
    updated = {
        "category": "Meals",
        "amount": "125000",
        "expense_date": (date.today() - timedelta(days=1)).isoformat(),
        "receipt_number": "REJECT001",
        "description": "Meal expense for the approved project planning session",
    }
    response = client.post(f"/claims/{claim_id}/edit", data=updated)
    assert response.status_code == 302
    client.post(f"/claims/{claim_id}/submit")
    with app.app_context():
        claim = get_db().execute(
            "SELECT status, approval_comment FROM claims WHERE id=?", (claim_id,)
        ).fetchone()
        assert claim["status"] == "Submitted"
        assert claim["approval_comment"] is None


def test_validation_and_export(client, app):
    login(client, "employee1", "Employee@123")
    bad = client.post("/claims/new", data={
        "category": "Meals", "amount": "0", "expense_date": (date.today() + timedelta(days=1)).isoformat(),
        "receipt_number": "RC1", "description": "Short",
    })
    assert bad.status_code == 200
    assert b"whole-number amount" in bad.data
    assert b"Receipt number must" in bad.data
    assert b"Description must" in bad.data
    report = client.get("/reports/monthly")
    assert report.status_code == 200
    assert b"Print / Save as PDF" in report.data
    xlsx = client.get("/exports/claims.xlsx")
    assert xlsx.status_code == 200
    wb = load_workbook(BytesIO(xlsx.data), read_only=True)
    assert "All Claims" in wb.sheetnames
    assert "Summary" in wb.sheetnames


def test_five_failed_logins_lock_account(client, app):
    for _ in range(5):
        response = client.post("/login", data={"username": "employee1", "password": "wrong"})
        assert response.status_code == 200
    with app.app_context():
        user = get_db().execute("SELECT failed_attempts, locked_at FROM users WHERE username='employee1'").fetchone()
        assert user["failed_attempts"] == 5
        assert user["locked_at"] is not None
        failed_logs = get_db().execute("SELECT COUNT(*) FROM audit_log WHERE action='FAILED_LOGIN'").fetchone()[0]
        assert failed_logs >= 5


def test_audit_log_is_immutable(app):
    with app.app_context():
        db = get_db()
        audit_id = db.execute("SELECT id FROM audit_log LIMIT 1").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE audit_log SET action='CHANGED' WHERE id=?", (audit_id,))
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM audit_log WHERE id=?", (audit_id,))
        db.rollback()


def test_manager_cannot_approve_high_value_claim_but_director_can(client, app):
    login(client, "manager_it", "Manager@123")
    with app.app_context():
        claim_id = get_db().execute(
            """SELECT id FROM claims WHERE status='Submitted' AND department='Information Technology'
               AND amount>5000000 LIMIT 1"""
        ).fetchone()[0]
    denied = client.post(f"/approvals/{claim_id}/decision", data={
        "decision": "Approved", "comment": "This should be blocked by the approval limit."
    })
    assert denied.status_code == 403
    logout(client)

    login(client, "admin", "Admin@123")
    accepted = client.post(f"/approvals/{claim_id}/decision", data={
        "decision": "Approved", "comment": "Director reviewed the high-value claim and evidence."
    })
    assert accepted.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT status, approver_id FROM claims WHERE id=?", (claim_id,)).fetchone()
        admin_id = get_db().execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        assert row["status"] == "Approved"
        assert row["approver_id"] == admin_id


def test_admin_soft_delete_keeps_claim_row_and_audit_record(client, app):
    login(client, "admin", "Admin@123")
    with app.app_context():
        claim_id = get_db().execute("SELECT id FROM claims WHERE is_deleted=0 LIMIT 1").fetchone()[0]
    response = client.post(f"/claims/{claim_id}/delete", follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        claim = get_db().execute("SELECT is_deleted FROM claims WHERE id=?", (claim_id,)).fetchone()
        audit = get_db().execute("SELECT COUNT(*) FROM audit_log WHERE record_id=? AND action='DELETE'", (claim_id,)).fetchone()[0]
        assert claim["is_deleted"] == 1
        assert audit == 1
