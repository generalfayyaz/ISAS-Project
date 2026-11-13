# Expense Claim & Reimbursement System

A complete Flask + SQLite web application for an Information Systems Audit assignment. The project uses fictional users and dummy claim data only. It is designed for local demonstration and academic assessment, not for processing real university reimbursements.

## 1. Main features

- Login and logout with Werkzeug password hashing.
- Four roles: Employee, Manager, Finance, and Admin (Director).
- Server-side role-based access control; unauthorized requests return HTTP 403.
- Expense claim create, read, update, submit, approve, reject, pay, and soft-delete workflow.
- Manager approval limit up to IDR 5,000,000; claims above that amount require Admin / Director approval.
- Required approval comments, duplicate warnings, input validation, and claim status history.
- Append-only audit log with SQLite triggers that reject UPDATE and DELETE operations.
- Five-failed-login account lockout and 15-minute inactivity timeout.
- Dashboard with status totals, monthly chart, top categories, and role-specific pending work.
- Search, filters, sorting, and pagination for claim records.
- Monthly printable report and individual claim voucher with signature blocks.
- Audit exception report for high-value approvals, duplicate suspects, self-approval, and late payments.
- Excel `.xlsx` export with a styled claims sheet and summary sheet.

## 2. Project structure

```text
expense_claim_system/
├── app.py
├── config.py
├── db.py
├── security.py
├── seed.py
├── wsgi.py
├── requirements.txt
├── requirements-dev.txt
├── Procfile
├── run_windows.bat
├── README.md
├── SCREENSHOT_GUIDE.md
├── routes/
│   ├── auth.py
│   ├── main.py
│   ├── claims.py
│   ├── approvals.py
│   ├── finance.py
│   ├── admin.py
│   ├── reports.py
│   └── exports.py
├── services/
│   ├── claim_queries.py
│   ├── validation.py
│   └── workflow.py
├── scripts/
│   ├── seed_demo.py
│   └── unlock_account.py
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── auth/login.html
│   ├── claims/{index,form,detail}.html
│   ├── approvals/inbox.html
│   ├── finance/payments.html
│   ├── admin/{users,user_form,audit_log}.html
│   ├── reports/{monthly,voucher,exceptions}.html
│   └── errors/{403,404,500}.html
├── static/css/app.css
├── tests/test_app.py
└── instance/                  # SQLite database is created here on first start
```

## 3. Local setup

Requirements: Python 3.10 or newer. On Windows, the easiest way is to extract the ZIP and double-click `run_windows.bat`. It creates a virtual environment, installs the requirements, and starts the application.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; python app.py
```

### macOS / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python app.py
```

Open **http://127.0.0.1:5000**.

On first start, the application creates the SQLite database and seeds 8 demo accounts plus 60 claim records. The seed runs only when the users table is empty. The app does not require a separate migration or seed command for its first local run.

To reset the local demo data, stop the application and run:

```bash
python scripts/seed_demo.py
```

This reset deletes and rebuilds the local demo database. Do not run it against data you need to keep.

If the only Admin account becomes locked and no other Admin can unlock it, stop the app and run `python scripts/unlock_account.py admin` from the project folder. This is a local recovery utility; regular unlocks should be performed from Admin → Users.

## 4. Demo accounts

All passwords are case-sensitive. These credentials are for a local academic demo and should be changed before any public deployment.

| Role | Username | Password | Department |
|---|---|---|---|
| Admin / Director | `admin` | `Admin@123` | Administration |
| Finance | `finance1` | `Finance@123` | Finance |
| Finance | `finance2` | `Finance@123` | Finance |
| Manager | `manager_it` | `Manager@123` | Information Technology |
| Manager | `manager_marketing` | `Manager@123` | Marketing |
| Employee | `employee1` | `Employee@123` | Information Technology |
| Employee | `employee2` | `Employee@123` | Information Technology |
| Employee | `employee3` | `Employee@123` | Marketing |

The fictional names and `.example.test` email addresses are generated for demonstration. No actual student or university employee data is used.

## 5. Role and permission model

| Function | Employee | Manager | Finance | Admin / Director |
|---|---:|---:|---:|---:|
| Create own claim | Yes | No | No | No |
| View own claims | Yes | — | — | Yes, all claims |
| Edit own Draft / Rejected claim | Yes | No | No | No |
| View department claims | No | Yes | No | Yes, all departments |
| Approve / reject up to IDR 5m | No | Own department | No | No |
| Approve / reject above IDR 5m | No | No | No | Yes |
| View Approved / Paid claims | Own claims | Own department | All | All |
| Mark Approved claim Paid | No | No | Yes | No |
| Manage users / audit logs | No | No | No | Yes |
| View audit exception report | No | No | No | Yes |
| Export Excel | Scoped to own claims | Scoped to department | Approved / Paid | All visible claims |

Access is checked in Flask route handlers and query scopes. Hiding a link in the interface is not the only security control.

## 6. Claim workflow and validation

```text
Employee creates Draft
        |
        v
Employee submits claim
        |
        v
     Submitted
        |
        +-- Amount <= IDR 5,000,000 --> Department Manager
        |
        +-- Amount >  IDR 5,000,000 --> Admin / Director
        |
        +------------------------------+
                       |
                 Approved / Rejected
                       |
        Rejected claim can be edited and resubmitted
                       |
                 Approved claim
                       |
                 Finance marks Paid
```

Validation rules enforced on the server:

- Required fields: category, description, amount, expense date, and receipt number.
- Amount: positive whole number, maximum IDR 100,000,000.
- Expense date: cannot be in the future or older than 90 days.
- Receipt number: 5–20 alphanumeric characters.
- Description: 10–255 characters.
- Approval and rejection comments: mandatory, at least 10 characters.
- Payment reference: 5–30 letters, numbers, or hyphens; payment date cannot be in the future.
- Potential duplicates are detected by employee + amount + expense date + receipt number. The user must acknowledge the warning before continuing.
- Paid claims are locked; claim deletion is a soft delete available to Admin only.

## 7. Audit controls implemented

| Audit control | Where it is implemented | Evidence to show |
|---|---|---|
| Authentication | `/login`, `/logout`; Werkzeug password hashes | Login page, dashboard after login, logout then login page; `LOGIN` / `LOGOUT` records |
| Account lockout | Login handler after 5 bad passwords | `FAILED_LOGIN` audit entries and locked account in Admin → Users |
| Session timeout | `security.py` checks last activity against 15 minutes | Wait 15 minutes without activity, then open a protected page |
| CSRF protection | Flask-WTF `CSRFProtect` on POST forms | Forms include a CSRF token; missing/invalid token is rejected |
| RBAC / least privilege | `roles_required`, visible-claim scopes, server-side query filters | Test Employee opening another employee's claim; expect HTTP 403 |
| Segregation of duties | Submitter ID cannot equal approver; Finance-only payment endpoint; approver cannot pay | Demonstrate manager approval and separate Finance payment account |
| Approval limit | `services/workflow.py` enforces Manager <= IDR 5m and Admin > IDR 5m | Manager cannot approve high-value claim; Admin sees Director inbox |
| Mandatory approval evidence | Approval and rejection comment requires 10+ characters | Try submitting a short comment; request is rejected |
| Audit trail | `audit_log` records authentication and transaction events | Admin → Audit log; filter by action or username |
| Audit immutability | SQLite triggers block UPDATE and DELETE on `audit_log` | Attempt a direct SQL UPDATE or DELETE; SQLite raises an error |
| Soft delete | `claims.is_deleted=1`; `DELETE` action recorded | Admin archives a claim; row remains stored and appears as archived in Admin claim list with Include archived |
| Duplicate detection | Employee, amount, date, and receipt comparison | Create a duplicate of an existing claim; warning appears before save |
| Payment control | Finance can pay only Approved claims; payment date/reference required | Finance → Payments; paid claim becomes locked |
| Output security | Jinja auto-escaping, parameterized SQLite queries, CSRF protection | Explain HTML escaping and parameter binding during the audit discussion |

### Seeded audit exceptions

The seed data intentionally contains a duplicate-suspect pair, a high-value claim that historically received Manager approval, and several payments delayed by more than 30 days. These are **historical dummy exceptions** so the Admin exception report has meaningful test results. The live workflow blocks a Manager from approving a claim above IDR 5,000,000. The seeded data contains no self-approved claim; the expected self-approval result is zero.

## 8. Reports and Excel export

- **Monthly report:** open Reports → Monthly report, select a month, then choose **Print / Save as PDF**. In the browser print dialog, select “Save as PDF”.
- **Claim voucher:** open a claim and select **Claim voucher**. The voucher has Employee, Manager / Director, and Finance signature blocks. Select **Print / Save as PDF**.
- **Audit exception report:** Admin → Audit exceptions. The page identifies high-value claims, invalid approval routes, possible duplicate groups, self-approved claims, and payments taking more than 30 days.
- **Excel:** use Export to Excel. The `.xlsx` workbook contains an All Claims sheet and a Summary sheet. The export respects the same role access scope and any filters passed from the Claims page.

## 9. Screenshot guide for the five assignment requirements

Capture these exact screens. Use the demo accounts above and keep screenshots free of unrelated personal information.

| Assignment requirement | Page / action to capture | Suggested screenshot |
|---|---|---|
| 1. Login and logout | Capture `/login`; log in as `employee1` and capture the Dashboard; use Log out and capture the returned login page | `01-login-dashboard-logout.png` |
| 2. Transaction input and CRUD | Employee → Claims → New claim (Create); Claims register and claim detail (Read); open a Draft / Rejected claim and Edit (Update); Admin opens a claim and uses Archive claim (Delete / soft delete) | `02-claim-crud.png` |
| 3. Basic input validation | Employee → New claim; enter amount `0`, receipt `RC1`, a short description, or a date outside the allowed range; submit | `03-validation-errors.png` |
| 4. Printable / PDF report | Reports → Monthly report; choose a month with seeded data; capture the report and the browser print preview after pressing Print / Save as PDF | `04-monthly-report-pdf.png` |
| 5. Excel export | Claims → Export filtered Excel; open the downloaded `.xlsx` in Excel / LibreOffice and capture the All Claims sheet and Summary sheet | `05-excel-export.png` |

Extra audit evidence recommended: Admin → Audit log; Admin → Audit exceptions; Manager → Approval inbox; Finance → Payments; and the HTTP 403 page when an Employee tries to access another employee's claim.

## 10. Run the automated tests

Install the development requirements, then run:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests use a temporary SQLite database and do not modify the normal `instance/expense_claims.sqlite3` demo database.

## 11. Deployment: PythonAnywhere (primary free option)

PythonAnywhere is the recommended route for this SQLite demo because the application database is stored on the app's account filesystem. Current free accounts are limited (the published free-account page lists 100 CPU seconds, 512 MiB disk, one web app / one web worker, and a one-month expiry), so it is suitable for a small coursework demonstration, not a continuously available production system. Check the current plan page before deploying.

1. Create a PythonAnywhere account and open a Bash console.
2. Upload this project ZIP using the **Files** page and extract it, or clone your Git repository into `/home/YOUR_USERNAME/expense_claim_system`.
3. Create a virtual environment and install dependencies:

   ```bash
   mkvirtualenv --python=/usr/bin/python3.11 expense-venv
   pip install -r /home/YOUR_USERNAME/expense_claim_system/requirements.txt
   ```

   Choose a Python version available in the PythonAnywhere Web tab if `python3.11` is not offered for your account.

4. Open the **Web** tab → **Add a new web app** → choose Manual configuration and the same Python version used for the virtual environment.
5. In the Web tab, set the Virtualenv field to `/home/YOUR_USERNAME/.virtualenvs/expense-venv`.
6. Open the WSGI configuration file and replace its contents with the following. Replace `YOUR_USERNAME` and set a long random secret key:

   ```python
   import os
   import sys

   project_home = '/home/YOUR_USERNAME/expense_claim_system'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   os.environ['SECRET_KEY'] = 'replace-with-a-long-random-secret-value'
   os.environ['DATABASE_PATH'] = project_home + '/instance/expense_claims.sqlite3'
   os.environ['SEED_DATA'] = '1'

   from app import app as application
   ```

7. Make sure the `instance` folder is inside the project folder and writable by your account. Click **Reload** in the Web tab.
8. Open `https://YOUR_USERNAME.pythonanywhere.com`. The first app start creates the SQLite database and seeds the demo data.

When updating the code, upload the changed files and reload the web app. Back up `instance/expense_claims.sqlite3` before any replacement or reset. Do not share the demo passwords on a public website; change demo passwords and `SECRET_KEY` before presenting a public-facing deployment. Set `SESSION_COOKIE_SECURE=1` for the HTTPS deployment.

## 12. Render alternative (demo-only with SQLite)

A Flask web service can be deployed on Render with the included `Procfile`, but Render's free web services have an ephemeral filesystem. A local SQLite database can be lost when the service restarts, redeploys, or spins down. Free web services also spin down after inactivity. Therefore use Render only for a disposable demo where the seed data can be regenerated, or change the database to a persistent hosted database before relying on it for ongoing records.

1. Push the project to a GitHub repository.
2. In Render, choose **New → Web Service** and connect the repository.
3. Set Build Command to `pip install -r requirements.txt`.
4. Set Start Command to `gunicorn app:app`.
5. Set environment variables `SECRET_KEY` to a long random value, `SEED_DATA` to `1`, and `SESSION_COOKIE_SECURE` to `1` when using the HTTPS service URL.
6. Deploy and open the generated service URL. Remember that SQLite records are not durable on the free filesystem.

## 13. Configuration and important limitations

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | Development-only value | Flask session signing and CSRF protection; set a strong secret in deployment |
| `DATABASE_PATH` | `instance/expense_claims.sqlite3` | SQLite database file path |
| `SEED_DATA` | `1` | Seed 8 demo users and 60 claims if the user table is empty |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` when deployed behind HTTPS to require secure session cookies |
| `PORT` | `5000` | Local / container port |

This is a learning application. Before use in a real organization, it would need a formal security review, HTTPS and production configuration, backup/restore procedures, secure password reset and MFA, stronger session/device controls, privacy review, database migration management, approval-policy sign-off, file/receipt upload scanning, and operational monitoring. The current demo does not upload or store receipt images.
