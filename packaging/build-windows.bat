@echo off
REM ===================================================================
REM  Build NmapStudio.exe   -   double-click this file on Windows.
REM  Produces:  dist\NmapStudio.exe   (one single file, no install)
REM ===================================================================

setlocal
cd /d "%~dp0\.."

echo.
echo  [1/4] Checking Python...
where python >nul 2>nul || (
    echo.
    echo  Python was not found.
    echo  Install it from https://www.python.org/downloads/
    echo  and tick "Add python.exe to PATH" on the first screen.
    echo.
    pause & exit /b 1
)

echo  [2/4] Installing build requirements...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet PyQt6 pyinstaller pillow pywinpty || (
    echo.
    echo  Could not install the build requirements.
    pause & exit /b 1
)

echo  [3/4] Generating the application icon...
python packaging\make-icons.py

echo  [4/4] Building the executable ^(this takes a few minutes^)...
python -m PyInstaller --noconfirm --clean packaging\nmap-studio.spec || (
    echo.
    echo  The build failed. The output above says why.
    pause & exit /b 1
)

echo.
echo  ===================================================================
echo   Done.  Your program is:   dist\NmapStudio.exe
echo.
echo   Copy it anywhere and double-click it. Nothing else to install,
echo   except nmap itself: https://nmap.org/download.html
echo   For SYN scans / OS detection, right-click it -^> Run as administrator.
echo  ===================================================================
echo.
pause
