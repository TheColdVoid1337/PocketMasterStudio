@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "WINPY=research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe"
if exist "%WINPY%" (
 "%WINPY%" "tools\frida_capture.py" %*
) else (
 py -3 "tools\frida_capture.py" %*
)
set "RESULT=%ERRORLEVEL%"
echo [RESULT] %RESULT%
popd
pause
exit /b %RESULT%
