@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "WINPY=research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe"
set "ARGS=%*"
if "%~1"=="" (
 echo [CONFIG] Enter JSON config path relative to repo root.
 set /p "CFG=Config [tools\frida_examples\htkpa_stage24b.json]: "
 if not defined CFG set "CFG=tools\frida_examples\htkpa_stage24b.json"
 set /p "PID=Existing target PID (required): "
 if not defined PID (echo [ERROR] No PID supplied. & goto :fail)
 set "ARGS=--config "%CFG%" --pid %PID%"
)
if exist "%WINPY%" (
 "%WINPY%" "tools\frida_capture.py" %ARGS%
) else (
 py -3 "tools\frida_capture.py" %ARGS%
)
set "RESULT=%ERRORLEVEL%"
echo [RESULT] %RESULT%
popd
pause
exit /b %RESULT%
:fail
popd
pause
exit /b 2
