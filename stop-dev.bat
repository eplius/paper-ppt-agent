@echo off
setlocal

taskkill /FI "WINDOWTITLE eq Paper PPT Agent Backend" /T /F >nul 2>nul
if errorlevel 1 (
  echo Backend window was not running.
) else (
  echo Backend stopped.
)

taskkill /FI "WINDOWTITLE eq Paper PPT Agent Frontend" /T /F >nul 2>nul
if errorlevel 1 (
  echo Frontend window was not running.
) else (
  echo Frontend stopped.
)

endlocal
