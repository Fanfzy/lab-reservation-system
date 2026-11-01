@rem Launcher section: use the existing dedicated Conda environment.
@echo off
rem Keep process variables local to this window.
setlocal
rem Python prints Chinese text using UTF-8; batch control text stays ASCII.
chcp 65001 >nul
rem Work in the real project directory.
cd /d "%~dp0"
rem Allow an explicit environment path on another device.
if not defined LAB_BOOKING_PYTHON set "LAB_BOOKING_PYTHON=D:\conda_envs\lab_booking\python.exe"
rem Serve only the local machine, using port 8000 by default.
if not defined LAB_BOOKING_PORT set "LAB_BOOKING_PORT=8000"
rem Use consistent Python output encoding.
set "PYTHONIOENCODING=utf-8"
rem Never install an environment automatically.
if not exist "%LAB_BOOKING_PYTHON%" goto missing
rem Check port availability and print Chinese instructions from Python.
"%LAB_BOOKING_PYTHON%" -B scripts\check_local_port.py "%LAB_BOOKING_PORT%"
rem Do not migrate or start another server when the port check fails.
if errorlevel 1 goto port_failed
rem Apply existing migrations without clearing data.
"%LAB_BOOKING_PYTHON%" -B manage.py migrate --noinput
rem Stop when database preparation fails.
if errorlevel 1 goto failed
rem Start the local demonstration server without a reloader process.
"%LAB_BOOKING_PYTHON%" -B manage.py runserver 127.0.0.1:%LAB_BOOKING_PORT% --noreload --insecure
rem Preserve the real server exit status before any other command.
set "LAB_SERVER_RESULT=%errorlevel%"
rem Keep diagnostics visible when the server fails.
if not "%LAB_SERVER_RESULT%"=="0" goto server_failed
rem Exit after a normal server stop.
exit /b 0

rem Recovery section: missing interpreter.
:missing
rem Refer to the existing environment instructions.
echo Project Python was not found. See README.md.
rem Keep this window open for diagnosis.
pause
rem Return failure.
exit /b 1

rem Recovery section: failed database preparation.
:failed
rem Do not hide the preceding database error.
echo Database initialization failed. See the message above.
rem Keep the error visible.
pause
rem Return failure.
exit /b 1

rem Recovery section: failed server start or runtime.
:server_failed
rem Point to the real error and configurable local port.
echo Server failed. See the message above. Check LAB_BOOKING_PORT.
rem Keep the server diagnostic visible.
pause
rem Return the original failure status.
exit /b %LAB_SERVER_RESULT%

rem Recovery section: invalid or occupied port.
:port_failed
rem Python already printed the Chinese reason and recovery instruction.
pause
rem Return failure without starting a second server.
exit /b 1
