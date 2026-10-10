@echo off
rem Deskrawl GUI launcher. Double-click to run; args pass through (e.g. launcher.bat --selftest)
cd /d %~dp0tools

set "PY=..\.venv-gui\Scripts\python.exe"
if not exist "%PY%" (
    echo [first run] creating venv and installing PySide6, please wait...
    python -m venv ..\.venv-gui || goto :err
    "%PY%" -m pip install -r ..\requirements-gui.txt || goto :err
)

"%PY%" -m deskrawl_gui %*
if errorlevel 1 goto :err
exit /b 0

:err
echo.
echo Failed to start. Please report the error message above.
pause
exit /b 1
