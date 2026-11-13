@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -m venv .venv
    if errorlevel 1 goto error
)
echo Installing project requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Starting Expense Claim ^& Reimbursement System...
".venv\Scripts\python.exe" app.py
pause
exit /b 0
:error
echo Setup failed. Check that Python is installed and internet access is available for pip.
pause
exit /b 1
