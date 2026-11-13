# Screenshot Guide — Assignment Requirements

Use the fictional demo accounts in `README.md`. For a clean evidence set, use the screenshots below in order.

| No. | Requirement | Exact page / action | What must be visible |
|---|---|---|---|
| 1 | Login and logout | Open `/login`, sign in as `employee1`, capture Dashboard, then click **Log out** and capture the login page again. | Login form, authenticated dashboard with employee role, and returned login page after logout. |
| 2 | Transaction input and CRUD | Employee → **Claims** → **New claim**; save a new Draft; open its detail; edit it; then sign in as Admin and archive a claim. | Create form, claim register/detail (Read), Edit form (Update), and Admin soft-delete confirmation / archived record (Delete). |
| 3 | Basic input validation | Employee → **New claim**. Try amount `0`, receipt `RC1`, description `Short`, and a future expense date. | Red field-level validation messages beside amount, receipt number, description, and date. |
| 4 | Printable / PDF report | **Monthly report** → choose `2026-11` or another populated month → **Print / Save as PDF**. | Monthly totals by department and category, report period, and browser print preview with “Save as PDF”. |
| 5 | Excel export | **Claims** → **Export filtered Excel**; open the downloaded `.xlsx` file. | `All Claims` sheet with formatted header and filtered records; `Summary` sheet with record count and status totals. |

## Extra evidence for an IS Audit explanation

- Manager → **Approval inbox**: show a claim in the manager's department and the mandatory comment field.
- Admin → **Approval inbox**: show a submitted claim above IDR 5,000,000 routed to the Director.
- Finance → **Payments**: show an approved claim and the payment date / reference fields.
- Admin → **Audit log**: filter by `FAILED_LOGIN`, `SUBMIT`, `APPROVE`, `REJECT`, `PAY`, or `EXPORT`.
- Admin → **Audit exceptions**: show the seeded duplicate, one incorrect historical high-value approval, the zero self-approval result, and delayed payment rows.
- While signed in as Employee, try to open another employee's claim URL; capture the HTTP 403 Access denied page.

For safety, do not enter actual personal, banking, or university reimbursement information. The seeded names and records are fictional.
