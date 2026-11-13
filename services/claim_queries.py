from db import get_db
from security import current_user


def build_claim_filters(args, user=None, include_deleted_default=False):
    user = user or current_user()
    db = get_db()
    conditions = []
    params = []
    role = user["role"]
    if role == "Employee":
        conditions.append("c.employee_id = ?")
        params.append(user["id"])
    elif role == "Manager":
        conditions.append("c.department = ?")
        params.append(user["department"])
    elif role == "Finance":
        conditions.append("c.status IN ('Approved','Paid')")
    if args.get("include_deleted") == "1" and role == "Admin":
        pass
    else:
        conditions.append("c.is_deleted = 0")
    for key, column in (("status", "c.status"), ("category", "c.category"), ("department", "c.department")):
        value = (args.get(key) or "").strip()
        if value:
            conditions.append(f"{column} = ?")
            params.append(value)
    q = (args.get("q") or "").strip()
    if q:
        conditions.append("(c.claim_no LIKE ? OR c.description LIKE ? OR c.receipt_number LIKE ? OR e.full_name LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])
    date_from = (args.get("date_from") or "").strip()
    date_to = (args.get("date_to") or "").strip()
    if date_from:
        conditions.append("c.expense_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("c.expense_date <= ?")
        params.append(date_to)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sort_map = {
        "date_asc": "c.expense_date ASC, c.id ASC",
        "date_desc": "c.expense_date DESC, c.id DESC",
        "amount_asc": "c.amount ASC",
        "amount_desc": "c.amount DESC",
        "status": "c.status ASC, c.expense_date DESC",
    }
    order = sort_map.get(args.get("sort"), "c.created_at DESC")
    query = f"""SELECT c.*, e.full_name AS employee_name, a.full_name AS approver_name
                FROM claims c JOIN users e ON e.id = c.employee_id
                LEFT JOIN users a ON a.id = c.approver_id {where}
                ORDER BY {order}"""
    return query, params


def filtered_claims(args, user=None):
    query, params = build_claim_filters(args, user)
    return get_db().execute(query, params).fetchall()
