from datetime import datetime
from io import BytesIO
from flask import Blueprint, make_response, request
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from db import get_db
from security import log_action, login_required
from services.claim_queries import filtered_claims

bp = Blueprint("exports", __name__, url_prefix="/exports")


@bp.route("/claims.xlsx")
@login_required
def claims_excel():
    rows = filtered_claims(request.args)
    wb = Workbook()
    ws = wb.active
    ws.title = "All Claims"
    headers = ["Claim No", "Employee", "Department", "Category", "Description", "Amount (IDR)",
               "Expense Date", "Receipt Number", "Status", "Approver", "Approval Comment",
               "Payment Date", "Payment Reference", "Created At", "Updated At", "Deleted"]
    ws.append(headers)

    def safe_excel_text(value):
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + value
        return value

    for row in rows:
        ws.append([
            safe_excel_text(row["claim_no"]), safe_excel_text(row["employee_name"]),
            safe_excel_text(row["department"]), safe_excel_text(row["category"]),
            safe_excel_text(row["description"]), row["amount"], row["expense_date"],
            safe_excel_text(row["receipt_number"]), safe_excel_text(row["status"]),
            safe_excel_text(row["approver_name"]), safe_excel_text(row["approval_comment"]),
            row["payment_date"], safe_excel_text(row["payment_reference"]),
            row["created_at"], row["updated_at"], "Yes" if row["is_deleted"] else "No",
        ])

    header_fill = PatternFill("solid", fgColor="17365D")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        values = [len(str(cell.value or "")) for cell in col]
        width = min(max(max(values, default=10) + 2, 12), 48)
        ws.column_dimensions[get_column_letter(col[0].column)].width = width

    summary = wb.create_sheet("Summary")
    summary.append(["Expense Claim Export Summary", ""])
    summary.append(["Generated at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    summary.append(["Records exported", len(rows)])
    summary.append(["Total amount (IDR)", sum(r["amount"] for r in rows)])
    summary.append([])
    summary.append(["Status", "Count", "Total Amount (IDR)"])
    status_map = {}
    for row in rows:
        status_map.setdefault(row["status"], [0, 0])
        status_map[row["status"]][0] += 1
        status_map[row["status"]][1] += row["amount"]
    for status in ("Draft", "Submitted", "Approved", "Rejected", "Paid"):
        count, total = status_map.get(status, [0, 0])
        summary.append([status, count, total])
    for cell in summary[1]:
        cell.font = Font(bold=True, size=14, color="17365D")
    for cell in summary[6]:
        cell.fill = header_fill
        cell.font = header_font
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 22
    summary.column_dimensions["C"].width = 26

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    log_action("EXPORT", None, None, {"type": "claims_xlsx", "record_count": len(rows), "filters": dict(request.args)})
    get_db().commit()
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = 'attachment; filename="expense_claims_export.xlsx"'
    return response
