@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0..\..\..\.."
if errorlevel 1 (
  echo [ERROR] Could not locate repository root.
  pause
  exit /b 1
)
set "CAPTURE=research\htkpa\stages\stage24b\one_click_capture.py"
set "WINPY=research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe"
echo [SETUP] Stage24B read-only Windows FIR generator capture
echo [SETUP] Working directory: %CD%
if exist "%WINPY%" (
  "%WINPY%" "%CAPTURE%" %*
) else (
  echo [WARN] Existing private Windows venv not found. Trying py -3.
  py -3 "%CAPTURE%" %*
)
set "RESULT=%ERRORLEVEL%"
echo.
echo [RESULT] Exit code: %RESULT%
echo [INFO] Find .tar.gz under research\_LOCAL_FILES\stage23w_native\stage24b_captures
popd
pause
exit /b %RESULT%
