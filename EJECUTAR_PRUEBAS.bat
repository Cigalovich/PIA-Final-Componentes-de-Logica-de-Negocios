@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
py -m pytest --cov=app --cov-report=term --cov-fail-under=80
pause
