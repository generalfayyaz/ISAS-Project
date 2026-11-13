import random
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash

from security import now_local

DEPARTMENTS = ["Information Technology", "Marketing"]

DEMO_USERS = [
    {"username": "admin", "full_name": "Avery Morgan", "email": "avery.morgan@example.test", "password": "Admin@123", "role": "Admin", "department": "Administration"},
    {"username": "finance1", "full_name": "Jordan Lee", "email": "jordan.lee@example.test", "password": "Finance@123", "role": "Finance", "department": "Finance"},
    {"username": "finance2", "full_name": "Taylor Reed", "email": "taylor.reed@example.test", "password": "Finance@123", "role": "Finance", "department": "Finance"},
    {"username": "manager_it", "full_name": "Morgan Chen", "email": "morgan.chen@example.test", "password": "Manager@123", "role": "Manager", "department": "Information Technology"},
    {"username": "manager_marketing", "full_name": "Casey Brown", "email": "casey.brown@example.test", "password": "Manager@123", "role": "Manager", "department": "Marketing"},
    {"username": "employee1", "full_name": "Riley Stone", "email": "riley.stone@example.test", "password": "Employee@123", "role": "Employee", "department": "Information Technology"},
    {"username": "employee2", "full_name": "Jamie Park", "email": "jamie.park@example.test", "password": "Employee@123", "role": "Employee", "department": "Information Technology"},
    {"username": "employee3", "full_name": "Alex Rivera", "email": "alex.rivera@example.test", "password": "Employee@123", "role": "Employee", "department": "Marketing"},
]


def seed_database(db):
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    rng = random.Random(20261113)
    now = now_local()
    now_s = now.isoformat(sep=" ")
    user_ids = {}
    for user in DEMO_USERS:
        cur = db.execute(
            """INSERT INTO users (username, full_name, email, password_hash, role, department, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (user["username"], user["full_name"], user["email"], generate_password_hash(user["password"]),
             user["role"], user["department"], now_s),
        )
        user_ids[user["username"]] = cur.lastrowid

    status_plan = (["Draft"] * 15 + ["Submitted"] * 10 + ["Approved"] * 15 +
                   ["Rejected"] * 8 + ["Paid"] * 12)
    categories = ["Travel", "Meals", "Accommodation", "Office Supplies", "Training", "Other"]
    descriptions = {
        "Travel": "Ground transportation for a university coordination meeting",
        "Meals": "Meal expense during an approved full-day project activity",
        "Accommodation": "One-night accommodation for an off-campus event",
        "Office Supplies": "Stationery and small office materials for the team",
        "Training": "Registration fee for a professional skills workshop",
        "Other": "Necessary operational expense for a department activity",
    }
    employee_usernames = ["employee1", "employee2", "employee3"]
    managers = {"Information Technology": user_ids["manager_it"], "Marketing": user_ids["manager_marketing"]}
    created_claims = []

    for i, status in enumerate(status_plan):
        emp_username = employee_usernames[i % len(employee_usernames)]
        employee = next(u for u in DEMO_USERS if u["username"] == emp_username)
        department = employee["department"]
        category = categories[i % len(categories)]
        amount = rng.choice([50000, 75000, 125000, 185000, 250000, 375000, 525000, 850000,
                             1250000, 1850000, 2750000, 4200000, 5750000, 7200000, 9500000, 12000000])
        days_ago = rng.randint(2, 88)
        if status == "Paid" and i - 48 < 3:
            days_ago = 70 + (i - 48) * 4
        expense_day = now.date() - timedelta(days=days_ago)
        receipt = f"RC{now.year}{i+1:05d}"
        description = descriptions[category]
        approver_id = None
        approval_comment = None
        payment_date = None
        payment_reference = None
        approved_at = rejected_at = paid_at = submitted_at = None
        if status in ("Approved", "Rejected", "Paid"):
            if amount > 5_000_000:
                approver_id = user_ids["admin"]
            else:
                approver_id = managers[department]
            approval_comment = "Reviewed against the supporting receipt and department purpose."
        if status == "Submitted":
            submitted_at = (datetime.combine(expense_day, datetime.min.time()) + timedelta(days=1)).isoformat(sep=" ")
        elif status in ("Approved", "Rejected", "Paid"):
            submitted_at = (datetime.combine(expense_day, datetime.min.time()) + timedelta(days=1)).isoformat(sep=" ")
            decision_dt = datetime.combine(expense_day, datetime.min.time()) + timedelta(days=2)
            if status == "Approved":
                approved_at = decision_dt.isoformat(sep=" ")
            else:
                rejected_at = decision_dt.isoformat(sep=" ")
        if status == "Paid":
            # A few intentionally late payments make the audit exception report useful.
            delay = [38, 43, 52][i - 48] if i - 48 < 3 else rng.randint(4, 25)
            pay_day = expense_day + timedelta(days=delay)
            if pay_day > now.date():
                pay_day = now.date()
            payment_date = pay_day.isoformat()
            payment_reference = f"PAY{now.year}{i+1:05d}"
            paid_at = datetime.combine(pay_day, datetime.min.time()).isoformat(sep=" ")

        # Two records intentionally share employee, amount, expense date and receipt number.
        if i in (0, 15):
            emp_username = "employee1"
            employee = next(u for u in DEMO_USERS if u["username"] == emp_username)
            department = employee["department"]
            amount = 425000
            expense_day = now.date() - timedelta(days=12)
            receipt = "DUPL2026A"
            category = "Meals"
            description = "Duplicate-suspect meal expense for audit testing"
            approver_id = None
            approval_comment = None
            approved_at = rejected_at = None
            if status == "Submitted":
                submitted_at = (datetime.combine(expense_day, datetime.min.time()) + timedelta(days=1)).isoformat(sep=" ")
            if status in ("Approved", "Rejected", "Paid"):
                approver_id = managers[department]
                approval_comment = "Reviewed with the receipt attached to the claim."
                if status == "Approved":
                    approved_at = (datetime.combine(expense_day, datetime.min.time()) + timedelta(days=2)).isoformat(sep=" ")
                else:
                    rejected_at = (datetime.combine(expense_day, datetime.min.time()) + timedelta(days=2)).isoformat(sep=" ")

        # One historical exception is seeded to demonstrate the approval-limit test.
        if i == 25:
            amount = 8_250_000
            approver_id = managers[department]  # Incorrect historical route: Manager approved a > IDR 5m claim.
            approval_comment = "Historical seeded exception: manager approval exceeded the configured limit."
            status = "Approved"
            approved_at = (datetime.combine(expense_day, datetime.min.time()) + timedelta(days=2)).isoformat(sep=" ")

        created_dt = datetime.combine(expense_day, datetime.min.time()) + timedelta(hours=9)
        last_event = paid_at or approved_at or rejected_at or submitted_at
        updated_dt = datetime.fromisoformat(last_event) if last_event else created_dt
        if updated_dt < created_dt:
            updated_dt = created_dt
        cur = db.execute(
            """INSERT INTO claims (claim_no, employee_id, department, category, description, amount,
               expense_date, receipt_number, status, approver_id, approval_comment, submitted_at,
               approved_at, rejected_at, payment_date, payment_reference, paid_at, created_at, updated_at, is_deleted)
               VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (user_ids[emp_username], department, category, description, amount, expense_day.isoformat(), receipt,
             status, approver_id, approval_comment, submitted_at, approved_at, rejected_at,
             payment_date, payment_reference, paid_at, created_dt.isoformat(sep=" "), updated_dt.isoformat(sep=" ")),
        )
        claim_id = cur.lastrowid
        claim_no = f"EXP-{now.year}-{claim_id:04d}"
        db.execute("UPDATE claims SET claim_no = ? WHERE id = ?", (claim_no, claim_id))
        created_claims.append({
            "id": claim_id, "claim_no": claim_no, "employee_id": user_ids[emp_username],
            "status": status, "approver_id": approver_id, "amount": amount,
            "expense_date": expense_day.isoformat(), "created_at": created_dt.isoformat(sep=" "),
            "submitted_at": submitted_at, "approved_at": approved_at, "rejected_at": rejected_at,
            "paid_at": paid_at, "payment_date": payment_date, "payment_reference": payment_reference,
        })

    # Seed append-only audit history matching the demo transactions.
    for item in created_claims:
        db.execute(
            """INSERT INTO audit_log (user_id, action, record_id, old_value, new_value, timestamp, ip_address)
               VALUES (?, 'CREATE', ?, NULL, ?, ?, '127.0.0.1')""",
            (item["employee_id"], item["id"], '{"status":"Draft"}', item["created_at"]),
        )
        if item["status"] != "Draft":
            submitted_time = item["submitted_at"] or item["created_at"]
            db.execute(
                """INSERT INTO audit_log (user_id, action, record_id, old_value, new_value, timestamp, ip_address)
                   VALUES (?, 'SUBMIT', ?, ?, ?, ?, '127.0.0.1')""",
                (item["employee_id"], item["id"], '{"status":"Draft"}', '{"status":"Submitted"}', submitted_time),
            )
        if item["status"] in ("Approved", "Rejected", "Paid"):
            action = "APPROVE" if item["status"] in ("Approved", "Paid") else "REJECT"
            when = item["approved_at"] or item["rejected_at"] or item["created_at"]
            db.execute(
                """INSERT INTO audit_log (user_id, action, record_id, old_value, new_value, timestamp, ip_address)
                   VALUES (?, ?, ?, ?, ?, ?, '127.0.0.1')""",
                (item["approver_id"], action, item["id"], '{"status":"Submitted"}',
                 '{"status":"' + item["status"] + '"}', when),
            )
        if item["status"] == "Paid":
            db.execute(
                """INSERT INTO audit_log (user_id, action, record_id, old_value, new_value, timestamp, ip_address)
                   VALUES (?, 'PAY', ?, ?, ?, ?, '127.0.0.1')""",
                (user_ids["finance1"], item["id"], '{"status":"Approved"}',
                 '{"status":"Paid","payment_reference":"' + str(item["payment_reference"]) + '"}',
                 item["paid_at"] or item["created_at"]),
            )

    db.commit()
