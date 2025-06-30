@echo off
setlocal

REM --- Configuration ---
set VENV_DIR=venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
set REQUIREMENTS_FILE=requirements.txt
set MAIN_APP_FILE=main.py

echo Launching Fantasy Life i Mod Manager...
echo.

REM --- Check and Create Virtual Environment ---
if not exist "%VENV_DIR%\" (
    echo Creating virtual environment. This may take a moment...
    python -m venv "%VENV_DIR%"
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ERROR: Failed to create virtual environment.
        echo Please ensure Python 3.8+ is installed and accessible via your PATH.
        echo.
        pause
        exit /b %ERRORLEVEL%
    )
) else (
    echo Virtual environment already exists.
)

REM --- Activate Virtual Environment ---
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to activate virtual environment.
    echo Please check the '%VENV_DIR%\' folder for issues.
    echo.
    pause
    exit /b %ERRORLEVEL%
)

REM --- Install/Update Dependencies ---
REM pip is smart enough to only install/update what's needed.
REM This ensures all requirements are met without full re-installation.
echo Installing/Updating dependencies. This might take a moment if new dependencies are found...
pip install -r "%REQUIREMENTS_FILE%"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to install dependencies.
    echo Please check '%REQUIREMENTS_FILE%' and your internet connection.
    echo.
    pause
    exit /b %ERRORLEVEL%
)

REM --- Launch the Application ---
echo.
echo Launching %MAIN_APP_FILE%...
"%PYTHON_EXE%" "%MAIN_APP_FILE%"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: The application encountered an error and exited.
    echo Please check the console output above for details.
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Application finished.
pause

endlocal