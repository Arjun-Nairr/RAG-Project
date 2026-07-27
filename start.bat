@echo off
title RAG Study Assistant - Launcher

if not exist "%~dp0backend\venv\Scripts\python.exe" (
    echo Backend venv not found at backend\venv - set it up first:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    echo   copy .env.example .env   - then fill in GROQ_API_KEY and DATABASE_URL
    pause
    exit /b 1
)

if not exist "%~dp0frontend\node_modules" (
    echo Frontend dependencies not found - set them up first:
    echo   cd frontend
    echo   npm install
    pause
    exit /b 1
)

echo Starting backend (http://localhost:8000) and frontend (http://localhost:5173) ...
echo.

start "RAG Backend  :8000" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

start "RAG Frontend :5173" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Two windows just opened for the backend and frontend logs.
echo Close those windows (or press Ctrl+C inside them) to stop the servers.
echo.

%SystemRoot%\System32\ping.exe -n 7 127.0.0.1 >nul
start "" "http://localhost:5173"
