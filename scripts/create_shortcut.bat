@echo off
:: Creates a Desktop shortcut to BlogPilot.exe
:: Run this from the dist\BlogPilot\ folder OR pass the path as an argument.

SET "EXE_PATH=%~1"
IF "%EXE_PATH%"=="" SET "EXE_PATH=%~dp0..\dist\BlogPilot.exe"

IF NOT EXIST "%EXE_PATH%" (
    echo ERROR: BlogPilot.exe not found at: %EXE_PATH%
    echo Build the EXE first: pyinstaller blogpilot.spec
    pause
    EXIT /B 1
)

:: Get desktop path
FOR /F "tokens=2*" %%A IN ('REG QUERY "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop') DO SET "DESKTOP=%%B"

:: Create shortcut via PowerShell
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$sc = $ws.CreateShortcut('%DESKTOP%\BlogPilot.lnk');" ^
  "$sc.TargetPath = '%EXE_PATH%';" ^
  "$sc.WorkingDirectory = Split-Path '%EXE_PATH%';" ^
  "$sc.Description = 'BlogPilot — LinkedIn AI Growth Engine';" ^
  "$sc.Save();"

IF %ERRORLEVEL% EQU 0 (
    echo Desktop shortcut created: %DESKTOP%\BlogPilot.lnk
) ELSE (
    echo Failed to create shortcut. Try running as administrator.
)
pause
