@echo off
setlocal EnableExtensions
title PocketMaster Studio - Void's MOD
cd /d "%~dp0" || goto :no_folder

if not exist "PocketMasterStudio.html" (
  echo [ERROR] PocketMasterStudio.html not found beside START.bat.
  goto :fail
)
if not exist "tools\studio_server.py" (
  echo [ERROR] tools\studio_server.py not found.
  goto :fail
)

rem Use a native Windows Python, not the Linux-only WSL .venv.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>nul
  if not errorlevel 1 (
    py -3 "tools\studio_server.py" %*
    goto :finished
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>nul
  if not errorlevel 1 (
    python "tools\studio_server.py" %*
    goto :finished
  )
)

echo [ERROR] Windows Python 3.9+ was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo Or run from WSL: python3 tools/studio_server.py --no-browser
echo Then open http://127.0.0.1:8765/PocketMasterStudio.html in Windows Chrome.
goto :fail

:no_folder
echo [ERROR] Could not change to the Studio folder.
:fail
pause
exit /b 1

:finished
if errorlevel 1 (
  echo.
  echo [ERROR] The Studio server exited with an error.
  pause
  exit /b 1
)
endlocal
exit /b 0
