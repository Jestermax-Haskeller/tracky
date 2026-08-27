@echo off
setlocal EnableExtensions

REM Always build from the repository folder, even when this script is launched
REM from another Command Prompt or PowerShell working directory.
pushd "%~dp0"

REM Tracky targets 64-bit Python 3.14. The installer build uses a project-local
REM virtual environment so build dependencies do not modify global Python packages.
py -3.14 -c "import struct,sys; assert struct.calcsize('P') * 8 == 64; print(sys.version)" >nul 2>&1
if errorlevel 1 (
    echo Python 3.14 64-bit was not found.
    echo Install 64-bit Python 3.14 from python.org, including the Python Launcher.
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Tracky's build environment...
    py -3.14 -m venv .venv
    if errorlevel 1 goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

python -m pip install --upgrade pip
if errorlevel 1 goto :fail

python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

REM Clear stale packaging output before every setup build. PyInstaller's EXE is
REM only an intermediate file used by Inno Setup and is removed again on success.
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "installer_dist" rmdir /s /q "installer_dist"

echo.
echo Building tracky for the installer...
python -m PyInstaller --noconfirm --clean tracky.spec
if errorlevel 1 goto :fail

if not exist "dist\tracky.exe" (
    echo.
    echo PyInstaller finished without creating dist\tracky.exe.
    goto :fail
)

REM Inno Setup can be installed for only the current Windows account, machine-wide,
REM or exposed through PATH. Check all common locations so winget installations work.
set "ISCC="

if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)

if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC (
    for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do (
        if not defined ISCC set "ISCC=%%I"
    )
)

if not defined ISCC (
    echo.
    echo Inno Setup 6 was not found.
    echo Install it, then run build_installer.bat again.
    echo With winget: winget install JRSoftware.InnoSetup
    goto :fail
)

echo.
echo Using Inno Setup: %ISCC%
"%ISCC%" "%~dp0installer.iss"
if errorlevel 1 goto :fail

if not exist "%~dp0installer_dist\TrackySetup.exe" (
    echo.
    echo Installer compilation finished without creating TrackySetup.exe.
    goto :fail
)

REM Tracky is distributed through its setup program only. Remove the temporary
REM PyInstaller folders after Inno Setup has embedded the executable successfully.
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo Success: %~dp0installer_dist\TrackySetup.exe
echo.
echo The setup wizard will open now. Complete it to install tracky and register
echo it in Windows Settings ^> Apps ^> Installed apps.
start "" "%~dp0installer_dist\TrackySetup.exe"
popd
exit /b 0

:fail
echo.
echo Tracky installer build failed. Read the first error above for the cause.
popd
exit /b 1
