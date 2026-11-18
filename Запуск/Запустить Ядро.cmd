@echo off
setlocal
cd /d "%~dp0.."
title Yadro
if exist ".venv\Scripts\python.exe" goto dependencies
py -3.12 --version >nul 2>&1
if not errorlevel 1 goto create_py
python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 goto create_python
echo Python 3.12 is required. Install it, then open this file again.
echo The installer is python-3.12.10-amd64.exe in this folder.
goto error
:create_py
py -3.12 -m venv .venv
goto environment_ready
:create_python
python -m venv .venv
:environment_ready
if errorlevel 1 goto error
:dependencies
".venv\Scripts\python.exe" -c "import uvicorn, fastapi, pydantic, dotenv, httpx, bs4" >nul 2>&1
if not errorlevel 1 goto launch
echo Installing application dependencies. Internet access is needed for the first setup.
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto error
:launch
echo Starting Yadro. Keep this window open while using the website.
".venv\Scripts\python.exe" run.py --open-browser
if errorlevel 1 goto error
exit /b 0
:error
echo Yadro could not start. Copy the error above if you need help.
pause
exit /b 1
