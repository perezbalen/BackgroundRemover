@echo off
setlocal

cd /d "%~dp0"

set "VENV_DIR=.venv-win"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "GUI_EXE=%VENV_DIR%\Scripts\background-remover-gui.exe"

if not exist "%PYTHON_EXE%" (
    echo Creating Windows virtual environment in %VENV_DIR%...
    py -3.12 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create the virtual environment. Make sure Python 3.12 is installed.
        pause
        exit /b 1
    )
)

if not exist "%GUI_EXE%" (
    echo Installing app and GUI dependencies...
    "%PYTHON_EXE%" -m pip install -e ".[dev,gui]"
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Launching Aseprite Background Remover...
start "" "%GUI_EXE%"

