@echo off
setlocal EnableExtensions

REM Run from this repository regardless of the terminal's current directory.
pushd "%~dp0"

REM Development uses the same 64-bit Python 3.14 target as packaged builds.
py -3.14 -c "import struct,sys; assert struct.calcsize('P') * 8 == 64; print(sys.version)" >nul 2>&1
if errorlevel 1 (
    echo Python 3.14 64-bit was not found.
    echo Install 64-bit Python 3.14 from python.org, including the Python Launcher.
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    py -3.14 -m venv .venv
    if errorlevel 1 goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

python main.py
set "TRACKY_EXIT=%ERRORLEVEL%"
popd
exit /b %TRACKY_EXIT%

:fail
popd
exit /b 1
