@echo off
title Quantum Learning - Stop All Microservices
echo ============================================================
echo   Stopping All Microservices (Ports 5000, 5173, 8000, 8001, 8002, 8003, 8004, 8005)
echo ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set PYTHON=%ROOT%\web\backend\.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=%ROOT%\.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo Safely cleaning up microservice port listeners...
%PYTHON% -c "import subprocess; ports = ['5000', '5173', '8000', '8001', '8002', '8003', '8004', '8005']; res = subprocess.run(['netstat', '-ano'], capture_output=True, text=True); pids = set(); [pids.add(line.split()[-1]) for line in res.stdout.splitlines() if any(f':{p}' in line for p in ports) and 'LISTENING' in line]; [subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True) for pid in pids if pid != '0']; print('All microservice port listeners stopped cleanly.')"

echo ============================================================
echo   All microservices stopped cleanly!
echo ============================================================
pause
