@echo off
rem Build URH-NG for Windows (see build_windows.ps1 for the options).
rem Double-click it, or run it from a command prompt with options, e.g. to keep
rem all tools and temporary files on another drive:
rem    build.bat -WorkDir "D:\urh-ng build" -DepsDir "D:\urh-ng build\deps"
rem The log is written next to this file (build.log).
title Building URH-NG
rem -File passes the arguments unchanged, so paths with spaces or apostrophes work.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" %*
set "URH_BUILD_RC=%ERRORLEVEL%"
echo.
echo Finished with exit code %URH_BUILD_RC%. Log file: "%~dp0build.log"
if not defined URH_BUILD_NO_PAUSE pause
exit /b %URH_BUILD_RC%
