@echo off
setlocal
cd /d "%~dp0"

REM Runs FLiSaMM from source. Most users should download FLiSaMM.exe from the
REM Releases page instead.

set VENV_DIR=venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
set STAMP=%VENV_DIR%\requirements.installed

if not exist "%PYTHON_EXE%" (
    echo Creating virtual environment. This may take a moment...
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>nul
    if errorlevel 1 (
        echo.
        echo ERROR: Python 3.11 or newer is required and must be on your PATH.
        echo Download it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    python -m venv "%VENV_DIR%" || goto :fail
)

REM Only reinstall dependencies when requirements.txt has changed.
fc /b requirements.txt "%STAMP%" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    "%PYTHON_EXE%" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :fail
    copy /y requirements.txt "%STAMP%" >nul
)

"%PYTHON_EXE%" main.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo ERROR: Something went wrong. See the messages above, or the log in
echo %LOCALAPPDATA%\FLiSaMM\logs\flisamm.log
pause
exit /b 1
