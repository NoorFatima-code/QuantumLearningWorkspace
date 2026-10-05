@echo off
title Quantum Learning - Launch All Microservices
echo ============================================================
echo   Team Pluto - Quantum Learning Microservices
echo ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set PYTHON=%ROOT%\web\backend\.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=%ROOT%\.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [CLEANUP] Safely checking microservice ports (5000, 5173, 8000-8005)...
%PYTHON% -c "import subprocess; ports = ['5000', '5173', '8000', '8001', '8002', '8003', '8004', '8005']; res = subprocess.run(['netstat', '-ano'], capture_output=True, text=True); pids = set(); [pids.add(line.split()[-1]) for line in res.stdout.splitlines() if any(f':{p}' in line for p in ports) and 'LISTENING' in line]; [subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True) for pid in pids if pid != '0']; print('Target ports freed cleanly.')" >nul 2>&1

echo.

echo [1/8] Launching Pluto Backend (Port 5000)...
start "Pluto Backend - Port 5000" cmd /k "cd /d %ROOT%\web\backend && %PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 5000 --reload"
ping -n 3 127.0.0.1 >nul

echo [2/8] Launching Pluto Frontend (Port 5173)...
start "Pluto Frontend - Port 5173" cmd /k "cd /d %ROOT%\web\frontend && npm run dev"
ping -n 3 127.0.0.1 >nul

echo [3/8] Launching Mu Chatbot RAG (Port 8000)...
start "Mu Chatbot RAG - Port 8000" cmd /k "cd /d %ROOT%\chatbot\rag-engine && %PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8000"
ping -n 3 127.0.0.1 >nul

echo [4/8] Launching Lambda Ingestion Service (Port 8001)...
start "Lambda Ingestion - Port 8001" cmd /k "cd /d %ROOT%\ai-ml && %PYTHON% -m uvicorn ingestion.main:app --host 0.0.0.0 --port 8001"
ping -n 3 127.0.0.1 >nul

echo [5/8] Launching Lambda Quiz Generator (Port 8002)...
start "Lambda Quiz Generator - Port 8002" cmd /k "cd /d %ROOT%\ai-ml && %PYTHON% -m uvicorn quiz_generator.app.main:app --host 0.0.0.0 --port 8002"
ping -n 3 127.0.0.1 >nul

echo [6/8] Launching Lambda Weak Topic Detection (Port 8003)...
start "Lambda Weak Topic Detection - Port 8003" cmd /k "cd /d %ROOT%\ai-ml && %PYTHON% -m uvicorn weak_topic_detection.app.main:app --host 0.0.0.0 --port 8003"
ping -n 3 127.0.0.1 >nul

echo [7/8] Launching Lambda Roadmap Generator (Port 8004)...
start "Lambda Roadmap Generator - Port 8004" cmd /k "cd /d %ROOT%\ai-ml && %PYTHON% -m uvicorn roadmap_generator.app.main:app --host 0.0.0.0 --port 8004"
ping -n 3 127.0.0.1 >nul

echo [8/8] Launching Kappa Knowledge Graph (Port 8005)...
start "Kappa Knowledge Graph - Port 8005" cmd /k "cd /d %ROOT%\ai-ml && %PYTHON% -m uvicorn knowledge_graph.app.api.graph_routes:app --host 0.0.0.0 --port 8005"

echo.
echo ============================================================
echo   All 8 Microservices are launching!
echo.
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:5000
echo   Chatbot  : http://localhost:8000
echo   Ingestion: http://localhost:8001
echo   Quiz     : http://localhost:8002
echo   WeakTopic: http://localhost:8003
echo   Roadmap  : http://localhost:8004
echo   Graph    : http://localhost:8005
echo ============================================================
pause
