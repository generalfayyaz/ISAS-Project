import re
from datetime import date, timedelta
from flask import current_app
from security import now_local

RECEIPT_RE = re.compile(r"^[A-Za-z0-9]{5,20}$")


def validate_claim_form(form):
    errors = {}
    category = (form.get("category") or "").strip()
    description = (form.get("description") or "").strip()
    amount_raw = (form.get("amount") or "").strip()
    expense_date_raw = (form.get("expense_date") or "").strip()
    receipt = (form.get("receipt_number") or "").strip()

    if category not in current_app.config["CATEGORIES"]:
        errors["category"] = "Please choose a valid expense category."
    if len(description) < 10 or len(description) > 255:
        errors["description"] = "Description must contain 10–255 characters."
    try:
        if not re.fullmatch(r"\d+", amount_raw):
            raise ValueError
        amount = int(amount_raw)
        if amount <= 0 or amount > current_app.config["MAX_CLAIM_AMOUNT"]:
            raise ValueError
    except ValueError:
        amount = None
        errors["amount"] = "Enter a whole-number amount from IDR 1 to IDR 100,000,000."
    try:
        expense_date = date.fromisoformat(expense_date_raw)
        today = now_local().date()
        if expense_date > today:
            errors["expense_date"] = "Expense date cannot be in the future."
        elif expense_date < today - timedelta(days=90):
            errors["expense_date"] = "Expense date cannot be older than 90 days."
    except ValueError:
        expense_date = None
        errors["expense_date"] = "Enter a valid expense date."
    if not RECEIPT_RE.fullmatch(receipt):
        errors["receipt_number"] = "Receipt number must be 5–20 alphanumeric characters."
    return errors, {
        "category": category,
        "description": description,
        "amount": amount,
        "expense_date": expense_date_raw,
        "receipt_number": receipt,
    }
