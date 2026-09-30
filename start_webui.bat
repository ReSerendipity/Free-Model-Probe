@echo off
REM Project root launcher: start the connectivity test Web UI.
REM The UI listens on http://127.0.0.1:8777 (override with PORT=9000 before running).
cd /d "%~dp0webui"
echo Starting connectivity test Web UI ...
echo   URL: http://127.0.0.1:8777
echo   Press Ctrl+C to stop.
echo.
python server.py
if errorlevel 1 (
  echo.
  echo Failed to start: python may not be in PATH.
  echo Try a full path, e.g.:
  echo   "C:\Users\Doro\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe" server.py
  pause
)
