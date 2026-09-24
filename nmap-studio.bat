@echo off
REM Nmap Studio launcher for Windows.
REM Double-click this file, or run it from a terminal. To scan with -sS, -O or
REM --traceroute, right-click and choose "Run as administrator".

setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0nmap-studio" %*
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0nmap-studio" %*
    goto :eof
)

echo Python 3 was not found on PATH.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
pause
