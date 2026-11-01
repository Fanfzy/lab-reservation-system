@rem Initialization section: use the existing dedicated Conda environment.
@echo off
rem Keep variables local to this process.
setlocal
rem Decode Chinese Python output using UTF-8.
chcp 65001 >nul
rem Work in the real project directory.
cd /d "%~dp0"
rem Prefer the explicitly selected interpreter.
if not defined LAB_BOOKING_PYTHON set "LAB_BOOKING_PYTHON=D:\conda_envs\lab_booking\python.exe"
rem Use consistent Python output encoding.
set "PYTHONIOENCODING=utf-8"
rem Stop when the dedicated environment is unavailable.
if not exist "%LAB_BOOKING_PYTHON%" exit /b 1
rem Create or update tables without clearing current data.
"%LAB_BOOKING_PYTHON%" -B manage.py migrate --noinput
rem Do not seed data after a migration failure.
if errorlevel 1 exit /b 1
rem Fill only missing demonstration data through the real command.
"%LAB_BOOKING_PYTHON%" -B manage.py seed_demo
rem Save the initialization result before waiting for user input.
set "LAB_SEED_RESULT=%errorlevel%"
rem Keep the actual initialization output visible.
pause
rem Return the original initialization result.
exit /b %LAB_SEED_RESULT%
