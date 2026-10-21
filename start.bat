@echo off
chcp 65001 >nul
cd /d %~dp0
set HOST=127.0.0.1
set PORT=5001
if exist .venv\Scripts\python.exe (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=python
)
echo ====================================
echo  BasinScope
echo  http://127.0.0.1:5001
echo ====================================
"%PY%" app.py
pause
