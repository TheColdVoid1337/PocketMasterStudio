@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "WINPY=research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe"
set "ARGS=%*"
if "%~1"=="" (
 echo [CONFIG] Using Stage24C XMM example, automatic Manager PID discovery.
 set "ARGS=--config tools\frida_examples\htkpa_stage24c_xmm.json --module-file research\_LOCAL_FILES\vendor\5868USB.dll"
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
