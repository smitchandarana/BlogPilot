@echo off
echo ============================================
echo   BlogPilot — Build EXE
echo ============================================
echo.

:: Step 1: Build React frontend
echo [1/3] Building React frontend...
cd ui
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
cd ..
echo       Frontend built successfully.
echo.

:: Step 2: Install PyInstaller if missing
echo [2/3] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo       Installing PyInstaller...
    pip install pyinstaller
)
echo       PyInstaller ready.
echo.

:: Step 3: Build EXE
echo [3/3] Building EXE with PyInstaller...
pyinstaller blogpilot.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD COMPLETE
echo   Output: dist\BlogPilot\BlogPilot.exe
echo ============================================
echo.
echo IMPORTANT: The EXE contains NO API keys or passwords.
echo Users must configure credentials via the Settings page on first run.
echo.
pause
