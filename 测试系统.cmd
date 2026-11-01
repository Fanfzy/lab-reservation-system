@rem Test section: use the existing dedicated Conda environment.
@echo off
rem Keep variables local to this process.
setlocal
rem Decode Chinese Python output using UTF-8.
chcp 65001 >nul
rem Work in the real project directory.
cd /d "%~dp0"
rem Prefer the selected interpreter over any global Python.
if not defined LAB_BOOKING_PYTHON set "LAB_BOOKING_PYTHON=D:\conda_envs\lab_booking\python.exe"
rem Use consistent Python output encoding.
set "PYTHONIOENCODING=utf-8"
rem Stop when the dedicated environment is unavailable.
if not exist "%LAB_BOOKING_PYTHON%" exit /b 1
rem Run actual business, HTTP, concurrency and delivery tests.
"%LAB_BOOKING_PYTHON%" -B manage.py test tests --noinput -v 2
rem Save the test result before waiting for user input.
set "LAB_TEST_RESULT=%errorlevel%"
rem Keep the real test output visible.
pause
rem Return the original test result.
exit /b %LAB_TEST_RESULT%
