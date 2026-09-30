@echo off
REM Connectivity Test Web UI launcher
REM If python is not in PATH, replace "python" below with a full path, e.g.:
REM   "C:\Users\Doro\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe" server.py
cd /d "%~dp0"
python server.py
if errorlevel 1 (
  echo.
  echo Failed to start: python may not be in PATH.
  echo Use a full path to python.exe, or install Python first.
  pause
)
