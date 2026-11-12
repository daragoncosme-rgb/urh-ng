@echo off
rem Build URH-NG for Windows (see build_windows.ps1 for the options).
rem Example, keeping all tools and temporary files on drive G:
rem    build.bat -WorkDir G:\urh-ng-build -DepsDir G:\urh-ng-build\deps
title Building URH-NG
setlocal
rem Save the script folder first: "shift" below also shifts %0
set "HERE=%~dp0"
set "REPO=%HERE%..\.."
set "LOG=%HERE%build.log"
set "WORK=%REPO%\build-windows"
:findwork
if "%~1"=="" goto run
if /i "%~1"=="-WorkDir" set "WORK=%~2"
shift
goto findwork
:run
if not exist "%WORK%\tmp" mkdir "%WORK%\tmp"
set "TEMP=%WORK%\tmp"
set "TMP=%WORK%\tmp"
set "PIP_CACHE_DIR=%WORK%\pip-cache"
echo Log file: %LOG%
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%HERE%build_windows.ps1' %* *>&1 | Tee-Object -FilePath '%LOG%'; exit $LASTEXITCODE"
echo Finished with exit code %ERRORLEVEL%
endlocal
timeout /t 30
